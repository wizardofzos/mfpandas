class DCOLLECT:

    def __init__(self, dcollect=None):
        """Initialize our DCOLLECT class.
        Recordlayout from: https://www.ibm.com/docs/en/zos/3.1.0?topic=output-dcollect-record-structure

        Args:
            dcollect (path, required): Path to dcollect file. Defaults to None.
        """

        self._dcolfile = dcollect 
        self.s
