from dlg.ddap_protocol import DROPStates
from dlg.drop import DataDROP, logger, track_current_drop
from dlg.io import NgasIO, NgasLiteIO
from dlg.meta import dlg_string_param, dlg_int_param


##
# @brief NGAS
# @details An archive on the Next Generation Archive System (NGAS).
# @par EAGLE_START
# @param category NGAS
# @param tag daliuge
# @param data_volume Data volume/5/Float/ComponentParameter/readwrite//False/False/Estimated size of the data contained in this node
# @param group_end Group end/False/Boolean/ComponentParameter/readwrite//False/False/Is this node the end of a group?
# @param ngasSrv NGAS Server/localhost/String/ComponentParameter/readwrite//False/False/The URL of the NGAS Server
# @param ngasPort NGAS Port/7777/Integer/ComponentParameter/readwrite//False/False/The port of the NGAS Server
# @param ngasFileId File ID//String/ComponentParameter/readwrite//False/False/File ID on NGAS (for retrieval only)
# @param ngasConnectTimeout Connection timeout/2/Integer/ComponentParameter/readwrite//False/False/Timeout for connecting to the NGAS server
# @param ngasMime NGAS mime-type/"text/ascii"/String/ComponentParameter/readwrite//False/False/Mime-type to be used for archiving
# @param ngasTimeout NGAS timeout/2/Integer/ComponentParameter/readwrite//False/False/Timeout for receiving responses for NGAS
# @param dummy dummy//Object/InputPort/readwrite//False/False/Dummy input port
# @param dummy dummy//Object/OutputPort/readwrite//False/False/Dummy output port
# @par EAGLE_END
class NgasDROP(DataDROP):
    """
    A DROP that points to data stored in an NGAS server
    """

    ngasSrv = dlg_string_param("ngasSrv", "localhost")
    ngasPort = dlg_int_param("ngasPort", 7777)
    ngasFileId = dlg_string_param("ngasFileId", None)
    ngasTimeout = dlg_int_param("ngasTimeout", 2)
    ngasConnectTimeout = dlg_int_param("ngasConnectTimeout", 2)
    ngasMime = dlg_string_param("ngasMime", "application/octet-stream")
    len = dlg_int_param("len", -1)
    ngas_checksum = None

    def initialize(self, **kwargs):
        if self.len == -1:
            # TODO: For writing the len field should be set to the size of the input drop
            self.len = self._size
        if self.ngasFileId:
            self.fileId = self.ngasFileId
        else:
            self.fileId = self.uid

    def getIO(self):
        try:
            ngasIO = NgasIO(
                self.ngasSrv,
                self.fileId,
                self.ngasPort,
                self.ngasConnectTimeout,
                self.ngasTimeout,
                length=self.len,
                mimeType=self.ngasMime,
            )
        except ImportError:
            logger.warning("NgasIO not available, using NgasLiteIO instead")
            ngasIO = NgasLiteIO(
                self.ngasSrv,
                self.fileId,
                self.ngasPort,
                self.ngasConnectTimeout,
                self.ngasTimeout,
                length=self.len,
                mimeType=self.ngasMime,
            )
        return ngasIO

    @track_current_drop
    def setCompleted(self):
        """
        Override this method in order to get the size of the drop set once it is completed.
        """
        # TODO: This implementation is almost a verbatim copy of the base class'
        # so we should look into merging them
        status = self.status
        if status == DROPStates.CANCELLED:
            return
        elif status == DROPStates.SKIPPED:
            self._fire("dropCompleted", status=status)
            return
        elif status not in [DROPStates.INITIALIZED, DROPStates.WRITING]:
            raise Exception(
                "%r not in INITIALIZED or WRITING state (%s), cannot setComplete()"
                % (self, self.status)
            )

        self._closeWriters()

        # here we set the size. It could happen that nothing is written into
        # this file, in which case we create an empty file so applications
        # downstream don't fail to read
        logger.debug("Trying to set size of NGASDrop")
        try:
            stat = self.getIO().fileStatus()
            logger.debug(
                "Setting size of NGASDrop %s to %s", self.fileId, stat["FileSize"]
            )
            self._size = int(stat["FileSize"])
            self.ngas_checksum = str(stat["Checksum"])
        except:
            # we''ll try this again in case there is some other issue
            # try:
            #     with open(self.path, 'wb'):
            #         pass
            # except:
            #     self.status = DROPStates.ERROR
            #     logger.error("Path not accessible: %s" % self.path)
            raise
            logger.debug("Setting size of NGASDrop to %s", 0)
            self._size = 0
        # Signal our subscribers that the show is over
        logger.debug("Moving %r to COMPLETED", self)
        self.status = DROPStates.COMPLETED
        self._fire("dropCompleted", status=DROPStates.COMPLETED)
        self.completedrop()

    @property
    def dataURL(self) -> str:
        return "ngas://%s:%d/%s" % (self.ngasSrv, self.ngasPort, self.fileId)

    # Override
    def generate_reproduce_data(self):
        if self.ngas_checksum is None or self.ngas_checksum == "":
            return {"fileid": self.ngasFileId, "size": self._size}
        return {"data_hash": self.ngas_checksum}
