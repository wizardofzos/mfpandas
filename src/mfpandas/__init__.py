class MFPandasException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

from .DCOLLECT import DCOLLECT 
from .IRRDBU00 import IRRDBU00 

