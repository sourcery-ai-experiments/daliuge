import argparse
import datetime
import json
import logging
import os
import pathlib
import signal
import sys
import threading
import time
import traceback
from json import JSONDecodeError
from typing import Union
from urllib.parse import urlparse
from jsonschema import validate, ValidationError

import uvicorn
from fastapi import FastAPI, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dlg import restutils, common
from dlg.clients import CompositeManagerClient
from dlg.common.reproducibility.constants import REPRO_DEFAULT
from dlg.common.reproducibility.reproducibility import init_lgt_repro_data
from dlg.dropmake.lg import GraphException
from dlg.dropmake.pg_manager import PGManager
from dlg.dropmake.scheduler import SchedulerException
from dlg.dropmake.web.translator_utils import file_as_string, lg_repo_contents, lg_path, lg_exists, \
    pgt_exists, pgt_path, pgt_repo_contents, prepare_lgt, unroll_and_partition_with_params

file_location = pathlib.Path(__file__).parent.absolute()
templates = Jinja2Templates(directory=file_location)

app = FastAPI()
app.mount("/static", StaticFiles(directory=file_location), name="static")
logger = logging.getLogger(__name__)

post_sem = threading.Semaphore(1)
gen_pgt_sem = threading.Semaphore(1)

global lg_dir
global pgt_dir
global pg_mgr
LG_SCHEMA = json.loads(file_as_string("lg.graph.schema", package="dlg.dropmake"))


@app.post("/jsonbody/lg")
def jsonbody_post_lg(
        lg_name: str = Body(),
        lg_content: str = Body(),
        rmode: str = Body(default=str(REPRO_DEFAULT.value)),
):
    """
    Post a logical graph JSON.
    """
    try:
        lg_content = json.loads(lg_content)
    except JSONDecodeError:
        logger.warning("Could not decode lgt %s", lg_name)
    lg_content = init_lgt_repro_data(lg_content, rmode)
    lg_path = pathlib.Path(lg_dir, lg_name)
    post_sem.acquire()
    try:
        with open(lg_path, "w") as lg_file:
            lg_file.write(json.dumps(lg_content))
    except Exception as e:
        return HTTPException(status_code=500,
                             detail="Failed to save logical graph {0}:{1}".format(lg_name, str(e)))
    finally:
        post_sem.release()


@app.get("/jsonbody/lg")
def jsonbody_get_lg(
        lg_name: str = Body()
):
    """
    Returns JSON representation of saved logical graph.
    """
    if lg_name is None or len(lg_name) == 0:
        all_lgs = lg_repo_contents()
        try:
            first_dir = next(iter(all_lgs))
            first_lg = first_dir + "/" + all_lgs[first_dir][0]
            lg_name = first_lg
        except StopIteration:
            return "Nothing found in dir {0}".format(lg_path)
    if lg_exists(lg_name):
        # print "Loading {0}".format(lg_name)
        lgp = lg_path(lg_name)
        with open(lgp, "r") as f:
            data = f.read()
        return data
    else:
        return HTTPException(status_code=404, detail="JSON graph {0} not found\n".format(lg_name))


@app.get("/jsonbody/pgt")
def jsonbody_get_pgt(
        pgt_name: str = Body()
):
    """
    Return JSON representation of a physical graph template
    """
    if pgt_exists(pgt_name):
        # print "Loading {0}".format(lg_name)
        pgt = pgt_path(pgt_name)
        with open(pgt, "r") as f:
            data = f.read()
        return data
    else:
        return HTTPException(status_code=404, detail="JSON graph {0} not found".format(pgt_name))


@app.get("/pg_viewer", response_class=HTMLResponse)
def load_pg_viewer(request: Request,
                   pgt_name: str = Body()
                   ):
    """
    Loads the physical graph viewer
    """
    if pgt_name is None or len(pgt_name) == 0:
        all_pgts = pgt_repo_contents()
        try:
            first_dir = next(iter(all_pgts))
            pgt_name = first_dir + os.sep + all_pgts[first_dir][0]
        except StopIteration:
            pgt_name = None
    if pgt_exists(pgt_name):
        tpl = templates.TemplateResponse("pg_viewer.html", {
            "request": request,
            "pgt_view_json_name": pgt_name,
            "partition_info": None,
            "title": "Physical Graph Template",
            "error": None
        })
        return tpl
    else:
        return HTTPException(status_code=404,
                             detail="Physical graph template view {0} not found {1}".format(
                                 pgt_name, pgt_dir))


@app.get("/show_gantt_chart", response_class=HTMLResponse)
def show_gantt_chart(
        request: Request,
        pgt_id: str = Body()
):
    """
    Interface to show the gantt chart
    """
    tpl = templates.TemplateResponse("matrix_vis.html", {
        "request": request,
        "pgt_view_json_name": pgt_id,
        "vis_action": "pgt_gantt_chart"
    })
    return tpl


@app.get("/pgt_gantt_chart")
def get_gantt_chart(
        pgt_id: str = Body()
):
    """
    Interface to retrieve a Gantt Chart matrix associated with a PGT
    """
    try:
        ret = pg_mgr.get_gantt_chart(pgt_id)
        return ret
    except GraphException as ge:
        return HTTPException(status_code=500, detail="Failed to generate Gantt chart for {0}: {1}"
                             .format(pgt_id, ge))


@app.get("/show_schedule_matrix", response_class=HTMLResponse)
def show_schedule_matrix(
        request: Request,
        pgt_id: str = Body()
):
    """
    Interface to show the schedule mat
    """
    tpl = templates.TemplateResponse("matrix_vis.html", {
        "request": request,
        "pgt_view_json_name": pgt_id,
        "vis_action": "pgt_schedule_mat"
    })
    return tpl


@app.get("/get_schedule_matrices")
def get_schedule_matrices(
        pgt_id: str = Body()
):
    """
    Interface to return all schedule matrices for a single pgt_id
    """
    try:
        ret = pg_mgr.get_schedule_matrices(pgt_id)
        return ret
    except Exception as e:
        return HTTPException(status_code=500, detail="Failed to get schedule matrices for {0}: {1}"
                             .format(pgt_id, e))


# ------ Graph deployment methods ------ #

@app.get("/gen_pgt", response_class=HTMLResponse)
def gen_pgt(
        request: Request,
        lg_name: str = Body(),
        rmode: str = Body(default=str(REPRO_DEFAULT.value)),
        test: str = Body(default="false"),
        algorithm: str = Body(default="none"),
        num_partitions: int = Body(default=1),
        num_islands: int = Body(default=0),
        partition_label: str = Body(default="Partition"),
        algorithm_parameters: dict = Body(default={}),
):
    if not lg_exists(lg_name):
        return HTTPException(status_code=404,
                             detail="Logical graph '{0}' not found".format(lg_name))
    try:
        lgt = prepare_lgt(lg_path(lg_name), rmode)
        test = test.lower() == "true"
        pgt = unroll_and_partition_with_params(lgt, test, algorithm, num_partitions, num_islands,
                                               partition_label, algorithm_parameters)
        num_partitions = 0  # pgt._num_parts;

        pgt_id = pg_mgr.add_pgt(pgt, lg_name)

        part_info = " - ".join(
            ["{0}:{1}".format(k, v) for k, v in pgt.result().items()]
        )
        tpl = templates.TemplateResponse("pg_viewer.html", {
            "request": request,
            "pgt_view_json_name": pgt_id,
            "partition_info": part_info,
            "title": "Physical Graph Template%s"
                     % ("" if num_partitions == 0 else "Partitioning"),
            "error": None
        })
        return tpl
    except GraphException as ge:
        return HTTPException(status_code=500,
                             detail="Invalid Logical Graph {1}: {0}".format(str(ge), lg_name))
    except SchedulerException as se:
        return HTTPException(status_code=500,
                             detail="Graph scheduling exception {1}: {0}".format(str(se), lg_name))
    except Exception:
        trace_msg = traceback.format_exc()
        return HTTPException(status_code=500,
                             detail="Graph partition exception {1}: {0}".format(trace_msg, lg_name))


@app.post("/gen_pgt", response_class=HTMLResponse)
def gen_pgt_post(
        request: Request,
        lg_name:str = Body(),
        json_data:str = Body(),
        rmode:str = Body(str(REPRO_DEFAULT.value)),
        test: str = Body(default="false"),
        algorithm: str = Body(default="none"),
        num_partitions: int = Body(default=1),
        num_islands: int = Body(default=0),
        partition_label: str = Body(default="Partition"),
        algorithm_parameters: dict = Body(default={}),
):
    """
    Translating Logical Graphs to Physical Graphs.
    Differs from get_pgt above by the fact that the logical graph data is POSTed
    to this route in a HTTP form, whereas gen_pgt loads the logical graph data
    from a local file
    """
    test = test.lower() == "true"
    try:
        logical_graph = json.loads(json_data)
        error = None
        try:
            validate(logical_graph, LG_SCHEMA)
        except ValidationError as ve:
            error = "Validation Error {1}: {0}".format(str(ve), lg_name)
        logical_graph = prepare_lgt(logical_graph, rmode)
        # LG -> PGT
        pgt = unroll_and_partition_with_params(logical_graph, test, algorithm, num_partitions, num_islands, partition_label, algorithm_parameters)
        pgt_id = pg_mgr.add_pgt(pgt, lg_name)

        part_info = " - ".join(
            ["{0}:{1}".format(k, v) for k, v in pgt.result().items()]
        )
        tpl = templates.TemplateResponse("pg_viewer.html", {
            "request": request,
            "pgt_view_json_name": pgt_id,
            "partition_info": part_info,
            "title": "Physical Graph Template%s"
                     % ("" if num_partitions == 0 else "Partitioning"),
            "error": None
        })
        return tpl
    except GraphException as ge:
        return HTTPException(status_code=500,
                             detail="Invalid Logical Graph {1}: {0}".format(str(ge), lg_name))
    except SchedulerException as se:
        return HTTPException(status_code=500,
                             detail="Graph scheduling exception {1}: {0}".format(str(se), lg_name))
    except Exception:
        trace_msg = traceback.format_exc()
        return HTTPException(status_code=500,
                             detail="Graph partition exception {1}: {0}".format(trace_msg, lg_name))


@app.get("/gen_pg", response_class=StreamingResponse)
def gen_pg(
        request: Request,
        pgt_id: str = Body(),
        dlg_mgr_deploy: Union[str, None] = Body(default=None),
        dlg_mgr_url: Union[str, None] = Body(default=None),
        dlg_mgr_host: Union[str, None] = Body(default=None),
        dlg_mgr_port: Union[int, None] = Body(default=None),
        tpl_nodes_len: int = Body(default=0)
):
    """
    RESTful interface to convert a PGT(P) into PG by mapping
    PGT(P) onto a given set of available resources
    """
    # if the 'deploy' checkbox is not checked,
    # then the form submission will NOT contain a 'dlg_mgr_deploy' field
    deploy = dlg_mgr_deploy is not None
    mprefix = ""
    pgtp = pg_mgr.get_pgt(pgt_id)
    if pgtp is None:
        return HTTPException(status_code=404,
                             detail="PGT(P) with id {0} not found in the Physical Graph Manager"
                             .format(pgt_id))

    pgtpj = pgtp._gojs_json_obj
    reprodata = pgtp.reprodata
    logger.info("PGTP: %s", pgtpj)
    num_partitions = len(list(filter(lambda n: "isGroup" in n, pgtpj["nodeDataArray"])))
    mport = 443
    if dlg_mgr_url is not None:
        mparse = urlparse(dlg_mgr_url)
        try:
            (mhost, mport) = mparse.netloc.split(":")
            mport = int(mport)
        except:
            mhost = mparse.netloc
            if mparse.scheme == "http":
                mport = 80
            elif mparse.scheme == "https":
                mport = 443
        mprefix = mparse.path
        if mprefix.endswith("/"):
            mprefix = mprefix[:-1]
    else:
        mhost = dlg_mgr_host
        if dlg_mgr_port is not None:
            mport = dlg_mgr_port
        else:
            mport = 443

    logger.debug("Manager host: %s", mhost)
    logger.debug("Manager port: %s", mport)
    logger.debug("Manager prefix: %s", mprefix)

    if mhost is None:
        if tpl_nodes_len > 0:
            nnodes = num_partitions
        else:
            return HTTPException(status_code=500,
                                 detail="Must specify DALiuGE manager host or tpl_nodes_len")

        pg_spec = pgtp.to_pg_spec([], ret_str=False, tpl_nodes_len=nnodes)
        pg_spec.append(reprodata)
        response = StreamingResponse(json.dumps(pg_spec))
        response.headers["Content-Disposition"] = "attachment; filename=%s" % pgt_id
        return response
    try:
        mgr_client = CompositeManagerClient(
            host=mhost, port=mport, url_prefix=mprefix, timeout=30
        )
        # 1. get a list of nodes
        node_list = mgr_client.nodes()
        # 2. mapping PGTP to resources (node list)
        pg_spec = pgtp.to_pg_spec(node_list, ret_str=False)

        if deploy:
            dt = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S.%f")
            ssid = "{0}_{1}".format(
                pgt_id.split(".graph")[0].split("_pgt")[0].split("/")[-1], dt
            )
            mgr_client.create_session(ssid)
            # print "session created"
            completed_uids = common.get_roots(pg_spec)
            pg_spec.append(reprodata)
            mgr_client.append_graph(ssid, pg_spec)
            # print "graph appended"
            mgr_client.deploy_session(ssid, completed_uids=completed_uids)
            # mgr_client.deploy_session(ssid, completed_uids=[])
            # print "session deployed"
            # 3. redirect to the master drop manager
            return RedirectResponse("http://{0}:{1}{2}/session?sessionId={3}".format(
                mhost, mport, mprefix, ssid
            ))
        else:
            response = StreamingResponse(json.dumps(pg_spec))
            response.headers["Content-Disposition"] = "attachment; filename=%s" % pgt_id
            return response
    except restutils.RestClientException as re:
        return HTTPException(status_code=500,
                             detail="Failed to interact with DALiUGE Drop Manager: {0}".format(re))
    except Exception as ex:
        logger.error(traceback.format_exc())
        return HTTPException(status_code=500,
                             detail="Failed to deploy physical graph: {0}".format(ex))


@app.get("/gen_pg_spec")
def gen_pg_spec(
        pgt_id: str = Body(),
        node_list: list = Body(default=[]),
        manager_host: str = Body(),
):
    """
    Interface to convert a PGT(P) into pg_spec
    """
    try:
        if manager_host == "localhost":
            manager_host = "127.0.0.1"
        logger.debug("pgt_id: %s", str(pgt_id))
        logger.debug("node_list: %s", str(node_list))
    except Exception as ex:
        logger.error("%s", traceback.format_exc())
        return HTTPException(status_code=500,
                             detail="Unable to parse json body of request for pg_spec: {0}".format(
                                 ex))
    pgtp = pg_mgr.get_pgt(pgt_id)
    if pgtp is None:
        return HTTPException(status_code=404,
                             detail="PGT(P) with id {0} not found in the Physical Graph Manager".format(
                                 pgt_id
                             ))
    if node_list is None:
        return HTTPException(status_code=500, detail="Must specify DALiuGE nodes list")

    try:
        pg_spec = pgtp.to_pg_spec([manager_host] + node_list, ret_str=False)
        root_uids = common.get_roots(pg_spec)
        response = StreamingResponse(json.dumps({"pg_spec": pg_spec, "root_uids": list(root_uids)}))
        response.content_type = "application/json"
        return response
    except Exception as ex:
        logger.error("%s", traceback.format_exc())
        return HTTPException(status_code=500, detail="Failed to generate pg_spec: {0}".format(ex))


@app.get("/gen_pg_helm")
def gen_pg_helm(
        pgt_id: str = Body()
):
    """
    Deploys a PGT as a K8s helm chart.
    """
    # Get pgt_data
    from ...deploy.start_helm_cluster import start_helm
    pgtp = pg_mgr.get_pgt(pgt_id)
    if pgtp is None:
        return HTTPException(status_code=404,
                             detail="PGT(P) with id {0} not found in the Physical Graph Manager"
                             .format(pgt_id))

    pgtpj = pgtp._gojs_json_obj
    logger.info("PGTP: %s", pgtpj)
    num_partitions = len(list(filter(lambda n: "isGroup" in n, pgtpj["nodeDataArray"])))
    # Send pgt_data to helm_start
    try:
        start_helm(pgtp, num_partitions, pgt_dir)
    except restutils.RestClientException as ex:
        logger.error(traceback.format_exc())
        return HTTPException(status_code=500,
                             detail="Failed to deploy physical graph: {0}".format(ex))
    # TODO: Not sure what to redirect to yet
    return "Inspect your k8s dashboard for deployment status"


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    tpl = templates.TemplateResponse("pg_viewer.html", {
        "request": request,
        "pgt_view_json_name": None,
        "partition_info": None,
        "title": "Physical Graph Template",
        "error": None
    })
    return tpl


def run(_, args):
    """
    FastAPI implementation of daliuge translator interface
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--lgdir",
        action="store",
        type=str,
        dest="lg_path",
        help="A path that contains at least one sub-directory, which contains logical graph files",
    )
    parser.add_argument(
        "-t",
        "--pgtdir",
        action="store",
        type=str,
        dest="pgt_path",
        help="physical graph template path (output)",
    )
    parser.add_argument(
        "-H",
        "--host",
        action="store",
        type=str,
        dest="host",
        default="0.0.0.0",
        help="logical graph editor host (all by default)",
    )
    parser.add_argument(
        "-p",
        "--port",
        action="store",
        type=int,
        dest="port",
        default=8084,
        help="logical graph editor port (8084 by default)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        default=False,
        help="Enable more logging",
    )

    options = parser.parse_args(args)

    if options.lg_path is None or options.pgt_path is None:
        parser.error("Graph paths missing (-d/-t)")
    elif not os.path.exists(options.lg_path):
        parser.error(f"{options.lg_path} does not exist")

    if options.verbose:
        fmt = logging.Formatter(
            "%(asctime)-15s [%(levelname)5.5s] [%(threadName)15.15s] "
            "%(name)s#%(funcName)s:%(lineno)s %(message)s"
        )
        fmt.converter = time.gmtime
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        logging.root.addHandler(stream_handler)
        logging.root.setLevel(logging.DEBUG)

    try:
        os.makedirs(options.pgt_path)
    except OSError:
        logging.warning("Cannot create path %s", options.pgt_path)

    global lg_dir
    global pgt_dir
    global pg_mgr

    lg_dir = options.lg_path
    pgt_dir = options.pgt_path
    pg_mgr = PGManager(pgt_dir)

    def handler(*_args):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    uvicorn.run(
        app=app,
        host=options.host,
        port=8084,
        debug=options.verbose
    )
