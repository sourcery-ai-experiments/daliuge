import logging
from dlg.manager import client

logger = logging.getLogger(__name__)


class NMAssigner:

    def __init__(self):
        self.DIMs = {}  # Set of DIMs   name -> (server, port)
        self.NMs = {}  # Set of NMs     name -> (server, port)
        self.assignments = {}  # Maps NMs to DIMs
        self.mm_client = client.MasterManagerClient()

    def add_dim(self, name, server, port):
        self.DIMs[name] = (server, port)
        self.mm_client.add_dim(server)
        self.allocate_nms()

    def add_nm(self, name, server, port):
        self.NMs[name] = (server, port)
        self.mm_client.add_node(server)
        self.allocate_nms()

    def remove_dim(self, name):
        server, port = self.DIMs[name]
        try:
            self.mm_client.remove_dim(server)
            # TODO: Handle removing assignments
        finally:
            del self.DIMs[name]
        return server, port

    def remove_nm(self, name):
        server, _ = self.NMs[name]
        try:
            self.mm_client.remove_node(server)
            # TODO: Handle removing assignments
        finally:
            del self.NMs[name]

    def allocate_nms(self):
        if self.DIMs == {}:
            for nm in self.assignments:
                logger.info("Letting NM %s know they have no DIM", nm)
                pass  # TODO: let NMs know they have no DIM
        elif len(self.DIMs.keys()) == 1:
            dim = list(self.DIMs.keys())[0]
            for nm in self.NMs.keys():
                if nm not in self.assignments:
                    logger.info("Adding NM %s to DIM %s", nm, dim)
                    # TODO: Actually add the mn
                    pass
                elif self.assignments[nm] not in self.DIMs:  # If we've removed a DIM
                    logger.info("Re-assigning %s to DIM %s", nm, dim)
                    # TODO: Actually re-assign the dim
        else:  # We have lots of DIMs
            # Will do nothing, it's up to the user/deployer to handle this.
            pass
