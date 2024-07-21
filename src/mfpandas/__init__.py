class MFPandasException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

from .dcollect import DCOLLECT 
from .irrdbu00 import IRRDBU00 

