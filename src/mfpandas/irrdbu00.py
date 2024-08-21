import importlib.resources
import json
import pandas as pd 

import math


# No mess with my header lines in XLSX
import pandas.io.formats.excel
pandas.io.formats.excel.ExcelFormatter.header_style = None

import threading
import time
from datetime import datetime

import xlsxwriter

import os
import glob

import warnings 

class StoopidException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class IRRDBU00:
    """

    :param irrdbu00: Full path to irrdbu00 file
    :type irrdbu00: str
    :param pickles: Full patch to folder with pre-saved pickle files (optional)
    :type pickles: str
    :param prefix: Prefix for pickle files (optional)
    :type prefix: str
    :raise StoopidException: If no irrdbu00 or pickles file specified


    Example usage::

        >>> from mfpandas import IRRDBU00
        >>> r = IRRDBU00(irrdbu00='/path/to/irrdbu00')         


    By issuing a ``.save_pickles(path='/tmp/pickles', prefix='demo-')`` after parsing the generated DataFrames will be
    saved as pickles so you don't have to reparse the entire IRRDBU00 again.
    You can then do::

        >>> from mfpandas import IRRDBU00
        >>> r = IRRDBU00(pickles='/tmp/pickles', prefix='demo-')

    Then there's no need to parse the data again. This enables you to store different unloads 
    and reuse them easily.

    See ``.save_pickles``. 

    Creating an IRRDBU00 file
    ^^^^^^^^^^^^^^^^^^^^^^^^^
    
    To create an IRRDBU00 dataset on z/OS amend and execute the following JCL::

        //UNLOAD   EXEC PGM=IRRDBU00,PARM=NOLOCKINPUT
        //SYSPRINT   DD SYSOUT=*
        //INDD1    DD   DISP=SHR,DSN=PATH.TO.YOUR.RACFDB
        //OUTDD    DD   DISP=(,CATLG,DELETE),
        //              DSN=YOUR.IRRDBU00.FILE,
        //              DCB=(RECFM=VB,LRECL=4096),
        //              SPACE=(CYL,(50,150),RLSE)

    Then, transfer “YOUR.IRRDBU00.FILE” to your machine. Make sure this is an ASCII transfer.
    


    """    
    # Our states
    STATE_BAD         = -1
    STATE_INIT        =  0
    STATE_PARSING     =  1
    STATE_READY       =  2


    # keep track of names used for a record type, record type + name must match those in offsets.json
    # A dict with 'key' -> RecordType and the following values:
    #   'name' -> Internal name (and prefix for pickle-files)
    #             'coincedentally' this is also the prefix of all the columns in the DataFrame
    #   'df'   -> name of internal df, exposed as a class property later 'without the _'

    _recordtype_info = {
    '0100': {'name':'GPBD', 'df':'_groups'},
    '0101': {'name':'GPSGRP', 'df':'_subgroups'},
    '0102': {'name':'GPMEM', 'df':'_connects'},
    '0103': {'name':'GPINSTD', 'df':'_groupUSRDATA'},
    '0110': {'name':'GPDFP', 'df':'_groupDFP'},
    '0120': {'name':'GPOMVS', 'df':'_groupOMVS'},
    '0130': {'name':'GPOVM', 'df':'_groupOVM'},
    '0141': {'name':'GPTME', 'df':'_groupTME'},
    '0151': {'name':'GPCSD', 'df':'_groupCSDATA'},
    '0200': {'name':'USBD', 'df':'_users'},
    '0201': {'name':'USCAT', 'df':'_userCategories'},
    '0202': {'name':'USCLA', 'df':'_userClasses'},
    '0203': {'name':'USGCON', 'df':'_groupConnect'},
    '0204': {'name':'USINSTD', 'df':'_userUSRDATA'}, 
    '0205': {'name':'USCON', 'df':'_connectData'},
    '0206': {'name':'USRSF', 'df':'_userRRSFdata'},
    '0207': {'name':'USCERT', 'df':'_userCERTname'},
    '0208': {'name':'USNMAP', 'df':'_userAssociationMapping'},
    '0209': {'name':'USDMAP', 'df':'_userDistributedIdMapping'},  
    '020A': {'name':'USMFA', 'df':'_userMFAfactor'},
    '020B': {'name':'USMPOL', 'df':'_userMFApolicies'},
    '0210': {'name':'USDFP', 'df':'_userDFP'},
    '0220': {'name':'USTSO', 'df':'_userTSO'},
    '0230': {'name':'USCICS', 'df':'_userCICS'},
    '0231': {'name':'USCOPC', 'df':'_userCICSoperatorClasses'},
    '0232': {'name':'USCRSL', 'df':'_userCICSrslKeys'},
    '0233': {'name':'USCTSL', 'df':'_userCICStslKeys'},
    '0240': {'name':'USLAN', 'df':'_userLANGUAGE'},
    '0250': {'name':'USOPR', 'df':'_userOPERPARM'},
    '0251': {'name':'USOPRP', 'df':'_userOPERPARMscope'},
    '0260': {'name':'USWRK', 'df':'_userWORKATTR'},
    '0270': {'name':'USOMVS', 'df':'_userOMVS'},
    '0280': {'name':'USNETV', 'df':'_userNETVIEW'},
    '0281': {'name':'USNOPC', 'df':'_userNETVIEWopclass'},
    '0282': {'name':'USNDOM', 'df':'_userNETVIEWdomains'},
    '0290': {'name':'USDCE', 'df':'_userDCE'},
    '02A0': {'name':'USOVM', 'df':'_userOVM'},
    '02B0': {'name':'USLNOT', 'df':'_userLNOTES'},
    '02C0': {'name':'USNDS', 'df':'_userNDS'},
    '02D0': {'name':'USKERB', 'df':'_userKERB'},
    '02E0': {'name':'USPROXY', 'df':'_userPROXY'},
    '02F0': {'name':'USEIM', 'df':'_userEIM'},
    '02G1': {'name':'USCSD', 'df':'_userCSDATA'},
    '1210': {'name':'USMFAC', 'df':'_userMFAfactorTags'},
    '0400': {'name':'DSBD', 'df':'_datasets'},
    '0401': {'name':'DSCAT', 'df':'_datasetCategories'},
    '0402': {'name':'DSCACC', 'df':'_datasetConditionalAccess'},
    '0403': {'name':'DSVOL', 'df':'_datasetVolumes'},
    '0404': {'name':'DSACC', 'df':'_datasetAccess'},
    '0405': {'name':'DSINSTD', 'df':'_datasetUSRDATA'},
    '0406': {'name':'DSMEM', 'df':'_datasetMember'},
    '0410': {'name':'DSDFP', 'df':'_datasetDFP'},
    '0421': {'name':'DSTME', 'df':'_datasetTME'},
    '0431': {'name':'DSCSD', 'df':'_datasetCSDATA'},
    '0500': {'name':'GRBD', 'df':'_generals'},
    '0501': {'name':'GRTVOL', 'df':'_generalTAPEvolume'},
    '0502': {'name':'GRCAT', 'df':'_generalCategories'},
    '0503': {'name':'GRMEM', 'df':'_generalMembers'},
    '0504': {'name':'GRVOL', 'df':'_generalTAPEvolumes'},
    '0505': {'name':'GRACC', 'df':'_generalAccess'},
    '0506': {'name':'GRINSTD', 'df':'_generalUSRDATA'},
    '0507': {'name':'GRCACC', 'df':'_generalConditionalAccess'},
    '0508': {'name':'GRFLTR', 'df':'_generalDistributedIdFilter'},
    '0509': {'name':'GRDMAP', 'df':'_generalDistributedIdMapping'},
    '0510': {'name':'GRSES', 'df':'_generalSESSION'},
    '0511': {'name':'GRSESE', 'df':'_generalSESSIONentities'},
    '0520': {'name':'GRDLF', 'df':'_generalDLFDATA'},
    '0521': {'name':'GRDLFJ', 'df':'_generalDLFDATAjobnames'},
    '0530': {'name':'GRSIGN', 'df':'_generalSSIGNON'}, 
    '0540': {'name':'GRST', 'df':'_generalSTDATA'},
    '0550': {'name':'GRSV', 'df':'_generalSVFMR'}, 
    '0560': {'name':'GRCERT', 'df':'_generalCERT'},
    '1560': {'name':'CERTN', 'df':'_generalCERTname'},
    '0561': {'name':'CERTR', 'df':'_generalCERTreferences'},
    '0562': {'name':'KEYR', 'df':'_generalKEYRING'},
    '0570': {'name':'GRTME', 'df':'_generalTME'},
    '0571': {'name':'GRTMEC', 'df':'_generalTMEchild'},
    '0572': {'name':'GRTMER', 'df':'_generalTMEresource'},
    '0573': {'name':'GRTMEG', 'df':'_generalTMEgroup'},
    '0574': {'name':'GRTMEE', 'df':'_generalTMErole'},
    '0580': {'name':'GRKERB', 'df':'_generalKERB'},
    '0590': {'name':'GRPROXY', 'df':'_generalPROXY'},
    '05A0': {'name':'GREIM', 'df':'_generalEIM'},
    '05B0': {'name':'GRALIAS', 'df':'_generalALIAS'}, 
    '05C0': {'name':'GRCDT', 'df':'_generalCDTINFO'},
    '05D0': {'name':'GRICTX', 'df':'_generalICTX'},
    '05E0': {'name':'GRCFDEF', 'df':'_generalCFDEF'},
    '05F0': {'name':'GRSIG', 'df':'_generalSIGVER'},
    '05G0': {'name':'GRCSF', 'df':'_generalICSF'},
    '05G1': {'name':'GRCSFK', 'df':'_generalICSFsymexportKeylabel'},
    '05G2': {'name':'GRCSFC', 'df':'_generalICSFsymexportCertificateIdentifier'},
    '05H0': {'name':'GRMFA', 'df':'_generalMFA'},
    '05I0': {'name':'GRMFP', 'df':'_generalMFPOLICY'},
    '05I1': {'name':'GRMPF', 'df':'_generalMFPOLICYfactors'},
    '05J1': {'name':'GRCSD', 'df':'_generalCSDATA'},
    '05K0': {'name':'GRIDTP', 'df':'_generalIDTFPARMS'},
    '05L0': {'name':'GRJES', 'df':'_generalJES'}
    }

    _recordname_type = {}    # {'GPBD': '0100', ....}
    _recordname_df = {}      # {'GPBD': '_groups', ....}

    for (rtype,rinfo) in _recordtype_info.items():
        _recordname_type.update({rinfo['name']: rtype})
        _recordname_df.update({rinfo['name']: rinfo['df']})
    
    # load irrdbu00 field definitions, save offsets in _recordtype_info
    # strictly speaking only needed for parse() function, but also not limited to one instance.
    with importlib.resources.open_text("mfpandas", "irrdbu00-offsets.json") as file:
        _offsets = json.load(file)
    for offset in _offsets:
        rtype = _offsets[offset]['record-type']
        if rtype in _recordtype_info.keys():
          _recordtype_info[rtype].update({"offsets": _offsets[offset]["offsets"]})
    try:
        del file, rtype, rinfo, offset, _offsets  # don't need these as class attributes
    except NameError:
        pass

    _grouptree          = None  # dict with lists
    _ownertree          = None  # dict with lists
    _grouptreeLines     = None  # df with all supgroups up to SYS1
    _ownertreeLines     = None  # df with owners up to SYS1 or user ID
    
    _accessKeywords = [' ','NONE','EXECUTE','READ','UPDATE','CONTROL','ALTER','-owner-']
    
    # errors
    errors = []

    def __init__(self, irrdbu00=None, pickles=None, prefix=''):
        self._state = self.STATE_INIT

        if not irrdbu00 and not pickles:
            self._state = self.STATE_BAD
            raise StoopidException('No irrdbu00 or pickles specified.')
        else:
            if not pickles:
                self._irrdbu00 = irrdbu00
                self._state    = self.STATE_INIT
                self._unloadlines = sum(1 for _ in open(self._irrdbu00, errors="ignore"))

        if pickles:
            # Read from pickles dir
            picklefiles = glob.glob(f'{pickles}/{prefix}*.pickle')
            self._starttime = datetime.now()
            self._records = {}
            self._unloadlines = 0
            
            for pickle in picklefiles:
                fname = os.path.basename(pickle)
                recordname = fname.replace(prefix,'').split('.')[0]
                if recordname in IRRDBU00._recordname_type:
                    recordtype = IRRDBU00._recordname_type[recordname]
                    dfname = IRRDBU00._recordname_df[recordname]
                    setattr(self, dfname, pd.read_pickle(pickle))
                    recordsRetrieved = len(getattr(self, dfname))
                    self._records[recordtype] = {
                      "seen": recordsRetrieved,
                      "parsed": recordsRetrieved
                    }
                    self._unloadlines += recordsRetrieved

            # create remaining public DFs as empty (think can be removed now too)
            for (rtype,rinfo) in IRRDBU00._recordtype_info.items():
                if not hasattr(self, rinfo['df']):
                    setattr(self, rinfo['df'], pd.DataFrame())
                    self._records[rtype] = {
                      "seen": 0,
                      "parsed": 0
                    }

            self._state = self.STATE_READY
            self._stoptime = datetime.now()

        else:
            # Running threads
            self.THREAD_COUNT = 0

            # list of parsed record-types
            self._records = {}

            # list with parsed records, ready to be imported into df
            self._parsed = {}
            for rtype in IRRDBU00._recordtype_info:
                self._parsed[rtype] = []

    @property
    def status(self):
        """
        Shows the current state of parsing.

        Will return a dictionary like below::

          {
            'status': status, 
            'input-lines': amount of lines in the irrdbu00 files, 
            'lines-read': how many records have been read, 
            'lines-parsed': how many records have been parsed, 
            'lines-per-second': how many lines per second, 
            'parse-time': total parse time,
            'error-lines': amount of lines from input file that yielded errors (see .errors)
          }

        Status can be one of:

        - Error
        - Initial Object
        - Still parsing your unload
        - Optimizing DataFrames
        - Ready

        """        
        seen = 0
        parsed = 0
        start  = "n.a."
        stop   = "n.a."
        speed  = "n.a."
        parsetime = "n.a."

        for r in self._records:
            seen += self._records[r]['seen']
            parsed += self._records[r]['parsed']

        if self._state == self.STATE_BAD:
            status = "Error"
        elif self._state == self.STATE_INIT:
            status = "Initial Object"
        elif self._state == self.STATE_PARSING:
            status = "Still parsing your unload"
            start  = self._starttime
            speed  = math.floor(seen/((datetime.now() -self._starttime).total_seconds()))
        elif self._state == self.STATE_READY:
            status = "Ready"
            speed  = math.floor(seen/((self._stoptime - self._starttime).total_seconds()))
            parsetime = (self._stoptime - self._starttime).total_seconds()
        else:
            status = "Limbo"     
        return {'status': status, 'input-lines': self._unloadlines, 'lines-read': seen, 'lines-parsed': parsed, 'lines-per-second': speed, 'parse-time': parsetime, 'error-lines': len(self.errors)}

    def parse_fancycli(self, save_pickles=False, prefix=''):
        print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - parsing {self._irrdbu00}')
        self.parse()
        while self._state < self.STATE_READY:
            progress =  math.floor(((sum(r['seen'] for r in self._records.values() if r)) / self._unloadlines) * 63)
            pct = (progress/63) * 100 # not as strange as it seems:)
            done = progress * '▉'
            todo = (63-progress) * ' '
            time.sleep(0.5)
            print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - progress: {done}{todo} ({pct:.2f}%)'.center(80), end="\r")
        # make completed line always show 100% :)
        print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - progress: {63*"▉"} ({100:.2f}%)'.center(80))
        for r in self._records.keys():
            print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - recordtype {r} -> {self.parsed(self._recordtype_info[r]["name"])} records parsed')
        print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - total parse time: {(self._stoptime - self._starttime).total_seconds()} seconds')
        print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - {len(self.errors)} input lines could not be parsed')
        for error in self.errors:
            print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")}   - {error}')
        if save_pickles:
            self.save_pickles(path=save_pickles,prefix=prefix)
            print(f'{datetime.now().strftime("%y-%m-%d %H:%M:%S")} - Pickle files saved to {save_pickles}')

    def parse(self):
        """
        Starts parsing the IRRDBU00 file in the backround (threaded).
        You can check progress with the .status property.

        """                
        pt = threading.Thread(target=self.parse_t)
        pt.start()
        return True

    def parse_t(self):
        # TODO: make this multiple threads (per record-type?)
        if self.THREAD_COUNT == 0:
            self._starttime = datetime.now()
            self._state = self.STATE_PARSING
        self.THREAD_COUNT += 1
        lineno = 0
        with open(self._irrdbu00, 'r', encoding="utf-8", errors="replace") as infile:
            for line in infile:
                lineno += 1
                r = line[:4]
                # check if we can support this recordtype 
                if r not in self._recordtype_info.keys():
                    self.errors.append(f"Unsupported recordtype '{r}' on line {lineno} ignored.")
                    continue
                if r in self._records:
                    self._records[r]['seen'] += 1
                else:
                    self._records[r] = {'seen': 1, 'parsed': 0}
                try:
                    offsets = IRRDBU00._recordtype_info[r]["offsets"]
                except:
                    offsets = False
                if offsets:
                    irrmodel = {}
                    for model in offsets:
                        start = int(model['start'])
                        end   = int(model['end'])
                        name  = model['field-name']
                        value = line[start-1:end].strip()
                        irrmodel[name] = str(value) 
                    self._parsed[r].append(irrmodel)
                    self._records[r]['parsed'] += 1
        # all models parsed :)

        # create the interal attribs according to recordtype_info dict
        for (rtype,rinfo) in IRRDBU00._recordtype_info.items():
                setattr(self, rinfo['df'], pd.DataFrame.from_dict(self._parsed[rtype]))



        self.THREAD_COUNT -= 1
        if self.THREAD_COUNT == 0:
            self._state = self.STATE_READY         
            self._stoptime = datetime.now()

        # clenaup some memory
        del self._parsed
        return True

    def parsed(self, rname):
        rtype = IRRDBU00._recordname_type[rname]
        return self._records[rtype]['parsed'] if rtype in self._records else 0
        
    def save_pickle(self, df='', dfname='', path='', prefix=''):     
        # Sanity check
        if self._state != self.STATE_READY:
            raise StoopidException('Not done parsing yet! (PEBKAM/ID-10T error)')
        
        df.to_pickle(f'{path}/{prefix}{dfname}.pickle')


    def save_pickles(self, path='/tmp', prefix=''):
        """
        Saves the generated DataFrames into pickles so you can quickly
        use them again in another run.

        :param path: Full path to folder of the pickle files (default=/tmp)
        :type path: str
        :param prefix: Prefix for pickle files (optional)
        :type prefix: str
        :raise StoopidException: If not done parsing yet
        :raise StoopidException: If path does not exist and cannot be created

        """   
        # Sanity check
        if self._state != self.STATE_READY:
            raise StoopidException('Not done parsing yet! (PEBKAM/ID-10T error)')
        # Is Path there ?
        if not os.path.exists(path):
            madedir = os.system(f'mkdir -p {path}')
            if madedir != 0:
                raise StoopidException(f'{path} does not exist, and cannot create')
        # Let's save the pickles
        for (rtype,rinfo) in IRRDBU00._recordtype_info.items():
            if rtype in self._records and self._records[rtype]['parsed']>0:
                self.save_pickle(df=getattr(self, rinfo['df']), dfname=rinfo['name'], path=path, prefix=prefix)
            else:
                # TODO: ensure consistent data, delete old pickles that were not saved
                pass


    def _generic2regex(selection, lenient='%&*'):
        ''' Change a RACF generic pattern into regex to match with text strings in pandas cells.  use lenient="" to match with dsnames/resources '''
        if selection in ('**',''):
            return '.*$'
        else:
            return selection.replace('*.**','`dot``ast`')\
                    .replace('.**',r'\`dot``dot``ast`')\
                    .replace('*',r'[\w@#$`lenient`]`ast`')\
                    .replace('%',r'[\w@#$]')\
                    .replace('.',r'\.')\
                    .replace('`dot`','.')\
                    .replace('`ast`','*')\
                    .replace('`lenient`',lenient)\
                    +'$'


    def _giveMeProfiles(self, df, selection=None, option=None):
        ''' Search profiles using the index fields.  selection can be str or tuple.  Tuples check for group + user id in connects, or class + profile key in generals.
        option controls how selection is interpreted, and how data must be returned:
        None is for (expensive) backward compatibility, returns a df with 1 profile.
        LIST returns a series for 1 profile, much faster and easier to process.
        '''
        if not selection:
            raise StoopidException('profile criteria not specified...')
        if option in (None,'LIST','L'):  # return 1 profile
            # 1 string, several strings in a tuple, or a mix of strings and None
            if type(selection)==str and not option:
                selection = [selection]  # [] forces return of a df, not a Series
            elif type(selection)==tuple:
                if any([s in (None,'**') for s in selection]):  # any qualifiers are a mask
                    selection = tuple(slice(None) if s in (None,'**') else s for s in selection),
                else:
                    selection = [selection]
            else:
                pass
            try:
                return df.loc[selection]
            except KeyError:
                if not option:  # return empty DataFrame with all the original columns
                    return df.head(0)
                else:  # return Series 
                    return []
        else:
            raise StoopidException(f'unexpected last parameter {option}')




        
    
    # start of custom preselected dataframes.
    @property
    def specials(self):
        """Returns a ``USBD``-dataframe with all users that have the special attribute
        """
        return self._users[self._users['USBD_SPECIAL'].to_numpy() == 'YES']

    @property
    def operations(self):
        """Returns a ``USBD``-dataframe with all users that have the operations attribute
        """        
        return self._users[self._users['USBD_OPER'].to_numpy() == 'YES']

    @property
    def auditors(self):
        """Returns a ``USBD``-dataframe with all users that have the auditor attribute
        """        
        return self._users[self._users['USBD_AUDITOR'].to_numpy() == 'YES']

    @property
    def revoked(self):
        """Returns a ``USBD``-dataframe with all users that are revoked
        """
        return self._users[self._users['USBD_REVOKE'].to_numpy() == 'YES']

    def user(self, userid=None):
        """Returns a ``USBD``-dataframe with for the selected userid (empty if non-existing user)
        """       
        return self._users[self._users['USBD_NAME'].to_numpy()==userid]

    def group(self, group=None):
        """Returns a ``GPBD``-dataframe for the selected group
        """        
        return self._groups[self._groups['GPBD_NAME'].to_numpy()==group]

    @property
    def emptyGroups(self):
        """Returns a ``GPBD``-dataframe of all groups that have no members.
        """
        if self._state != self.STATE_READY:
            raise StoopidException('Not done parsing yet! (PEBKAM/ID-10T error)')
        return self._groups.loc[~self.groups.GPBD_NAME.isin(self._connectData.USCON_GRP_ID)]
    

    @property
    def dataset(self, profile=None):
        """Returns a ``DSBD``-dataframe of the requested dataset.
        """
        return self.datasets[self.datasets['DSBD_NAME'].to_numpy()==profile]

    @property
    def datasetPermit(self, profile=None):
        """Returns a ``DSACC``-dataframe for the requested dataset.
        """
        return self.datasetAccess[self.datasetAccess['DSACC_NAME'].to_numpy()==profile]

    @property
    def uacc_read_datasets(self):
        """Returns a ``DSBD``-dataframe of all datasets that have UACC=READ (bad!)
        """
        return self._datasets[self._datasets['DSBD_UACC'].to_numpy()=="READ"]
    
    @property
    def uacc_update_datasets(self):
        """Returns a ``DSBD``-dataframe of all datasets that have UACC=UPDATE (really bad!)
        """        
        return self._datasets[self._datasets['DSBD_UACC'].to_numpy()=="UPDATE"]
    
    @property   
    def uacc_control_datasets(self):
        """Returns a ``DSBD``-dataframe of all datasets that have UACC=CONTROL (really bad!)
        """            
        return self._datasets[self._datasets['DSBD_UACC'].to_numpy()=="CONTROL"]
    
    @property
    def uacc_alter_datasets(self):
        """Returns a ``DSBD``-dataframe of all datasets that have UACC=ALTER (really bad!)
        """            
        return self._datasets[self._datasets['DSBD_UACC'].to_numpy()=="ALTER"]

    @property
    def orphans(self):
        """Returns a tuple of two dataframes ``datasetOrphans`` and ``generalOrphans``.
        these are formatted like the DataFrames you get with ``datasetAccess`` and 
        ``generalAccess`` except you'll only see those entries that have an AUTH_ID on the 
        accesslist that's no longer present in the database.

        :raises StoopidException: If no datasetAccess or generalAccess recordtypes parsed.
        :return: df, df
        :rtype: DataFrame
        """
        
        if self.parsed("DSACC") + self.parsed("GRACC") == 0:
            raise StoopidException('No dataset/general access records parsed! (PEBKAM/ID-10T error)')
            
        datasetOrphans = None
        generalOrphans = None

        if self.parsed("DSACC") > 0:
            self._datasetAccess = self._datasetAccess.assign(inGroups=self._datasetAccess.DSACC_AUTH_ID.isin(self._groups.GPBD_NAME))
            self._datasetAccess = self._datasetAccess.assign(inUsers=self._datasetAccess.DSACC_AUTH_ID.isin(self._users.USBD_NAME))
            datasetOrphans = self._datasetAccess.loc[(self._datasetAccess['inGroups'] == False) & (self._datasetAccess['inUsers'] == False) & (self._datasetAccess['DSACC_AUTH_ID'] != "*") & (self._datasetAccess['DSACC_AUTH_ID'] != "&RACUID")]
            self._datasetAccess.drop(columns=['inUsers', 'inGroups'], inplace=True)
            datasetOrphans.drop(columns=['inUsers', 'inGroups'], inplace=True)
        
        if self.parsed("GRACC") > 0:
                self._generalAccess = self._generalAccess.assign(inGroups=self._generalAccess.GRACC_AUTH_ID.isin(self._groups.GPBD_NAME))
                self._generalAccess = self._generalAccess.assign(inUsers=self._generalAccess.GRACC_AUTH_ID.isin(self._users.USBD_NAME))
                generalOrphans =  self._generalAccess.loc[(self._generalAccess['inGroups'] == False) & (self._generalAccess['inUsers'] == False) & (self._generalAccess['GRACC_AUTH_ID'] != "*") & (self._generalAccess['GRACC_AUTH_ID'] != "&RACUID")]
                self._generalAccess.drop(columns=['inUsers', 'inGroups'], inplace=True)
                generalOrphans.drop(columns=['inUsers', 'inGroups'], inplace=True)

        return datasetOrphans, generalOrphans

    def xls(self,fileName='irrdbu00.xlsx'):
        """Create an XLSX-sheet at ``fileName`` with the datasetaccess and generalaccess overviews.
        One tab per class, a row for every profile in the class and colums with authids.
        This does not take conditional access into account.

        :param fileName: full path to where to save the xlsx, defaults to 'irrdbu00.xlsx'
        :type fileName: str
        :raises StoopidException: If not done parsing yet.
        :raises StoopidException: If no ``DSACC`` or ``GRACC`` records parsed.
        """
        if self._state != self.STATE_READY:
            raise StoopidException('Not done parsing yet! (PEBKAM/ID-10T error)')

        if self.parsed("DSACC") + self.parsed("GRACC") == 0:
            raise StoopidException('No dataset/general access records parsed! (PEBKAM/ID-10T error)')

        writer = pd.ExcelWriter(f'{fileName}', engine='xlsxwriter')
        accessLevelFormats = {
                    'N': writer.book.add_format({'bg_color': 'silver'}),
                    'E': writer.book.add_format({'bg_color': 'purple'}),
                    'R': writer.book.add_format({'bg_color': 'yellow'}),
                    'U': writer.book.add_format({'bg_color': 'orange'}),
                    'C': writer.book.add_format({'bg_color': 'red'}),
                    'A': writer.book.add_format({'bg_color': 'red'}),
                    'D': writer.book.add_format({'bg_color': 'cyan'}), 
                    'T': writer.book.add_format({'bg_color': 'orange'}),
                }

        accessLevels = {
                    'NONE': 'N',
                    'EXECUTE': 'E',
                    'READ': 'R',
                    'UPDATE': 'U',
                    'CONTROL': 'C',
                    'ALTER': 'A',
                    'NOTRUST': 'D',
                    'TRUST': 'T'
                }

        format_br = writer.book.add_format({})
        format_br.set_rotation(90)
        format_nr = writer.book.add_format({})
        format_center = writer.book.add_format({})
        format_center.set_align('center')
        format_center.set_align('vcenter')

        ss = datetime.now()

        classes = self.generalAccess.groupby(['GRACC_CLASS_NAME'])
        for c in classes.groups:
            s = datetime.now()
            authIDsInClass = list(self.generalAccess.loc[self.generalAccess.GRACC_CLASS_NAME==c]['GRACC_AUTH_ID'].unique())
            profilesInClass = list(self.generalAccess.loc[self.generalAccess.GRACC_CLASS_NAME==c]['GRACC_NAME'].unique())
            longestProfile = 0
            for p in profilesInClass:
                if len(p) > longestProfile:
                    longestProfile = len(p)
            newdata = {}
            newdata['Profiles'] = []
            for id in authIDsInClass:
                newdata[id] = [None] * len(profilesInClass)
            classdata = classes.get_group(c)
            profiles = classdata.groupby(['GRACC_NAME'])
            for i,p in enumerate(profiles.groups):
                profiledata = profiles.get_group(p)
                newdata['Profiles'].append(p)
                users = profiledata.groupby(['GRACC_AUTH_ID'])
                for u in users.groups:
                    useraccess = users.get_group(u)['GRACC_ACCESS'].values[0]
                    newdata[u][i] = accessLevels[useraccess]
            df1 = pd.DataFrame(newdata)
            df1.to_excel(writer, sheet_name=c, index=False)
            worksheet = writer.sheets[c]
            worksheet.set_row(0, 64, format_br)
            worksheet.set_column(1, len(authIDsInClass)+1, 2, format_center )
            worksheet.autofit()
            worksheet.write(0, 0, 'Profile', format_nr)

            shared_strings = sorted(worksheet.str_table.string_table, key=worksheet.str_table.string_table.get)
            for i in range(len(authIDsInClass)+1):
                for j in range(len(profilesInClass)+1):
                    if i>0 and j>0:
                        rdict = worksheet.table.get(j,None)
                        centry = rdict.get(i,None)
                        if centry:
                            value = shared_strings[centry.string]
                            worksheet.write(j, i, value, accessLevelFormats[value])

        if self.parsed("DSBD") > 0:
            ss = datetime.now()
            profilesInClass = list(self.datasetAccess['DSACC_NAME'].unique())
            authIDsInClass = list(self.datasetAccess['DSACC_AUTH_ID'].unique())
            authids = 0
            longestProfile = 0
            for p in profilesInClass:
                if len(p) > longestProfile:
                    longestProfile = len(p)
            newdata = {}
            newdata['Profiles'] = []
            for id in authIDsInClass:
                    newdata[id] = [None] * len(profilesInClass)
            profiles = self.datasetAccess.groupby(['DSACC_NAME'])
            for i,p in enumerate(profiles.groups):
                profiledata = profiles.get_group(p)
                newdata['Profiles'].append(p)
                users = profiledata.groupby(['DSACC_AUTH_ID'])
                for u in users.groups:
                    useraccess = users.get_group(u)['DSACC_ACCESS'].values[0]
                    newdata[u][i] = accessLevels[useraccess]

            df1 = pd.DataFrame(newdata)
            df1.to_excel(writer, sheet_name='DATASET', index=False)
            worksheet = writer.sheets['DATASET']
            worksheet.set_row(0, 64, format_br)
            worksheet.set_column(1, len(authIDsInClass)+1, 2, format_center )
            worksheet.set_column(0, 0, longestProfile + 2 )
            worksheet.write(0, 0, 'Profile', format_nr)

            shared_strings = sorted(worksheet.str_table.string_table, key=worksheet.str_table.string_table.get)
            for i in range(len(authIDsInClass)+1):
                for j in range(len(profilesInClass)+1):
                    if i>0 and j>0:
                        rdict = worksheet.table.get(j,None)
                        centry = rdict.get(i,None)
                        if centry:
                            value = shared_strings[centry.string]
                            worksheet.write(j, i, value, accessLevelFormats[value])

        writer.close()   
   
    # endf of custom dataframes and functions

    # start of standard dataframes (1-on-1 recordtypes as dataframe) generated via genProps.py

    @property
    def groups(self):
        """Returns a DataFrame for the group basic data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ===============================================================================================================================================================
        Column            Description
        ================= ===============================================================================================================================================================
        GPBD_RECORD_TYPE  Record type of the Group Basic Data record (0100).
        GPBD_NAME         Group name as taken from the profile name.
        GPBD_SUPGRP_ID    Name of the superior group to this group.
        GPBD_CREATE_DATE  Date that the group was defined.
        GPBD_OWNER_ID     The user ID or group name which owns the profile.
        GPBD_UACC         The default universal access. Valid values are 
        GPBD_NOTERMUACC   Indicates if the group must be specifically authorized to use a particular terminal through the use of the PERMIT command. Valid Values include "Yes" and "No".
        GPBD_INSTALL_DATA Installation-defined data.
        GPBD_MODEL        Data set profile that is used as a model for this group.
        GPBD_UNIVERSAL    Indicates if the group has the UNIVERSAL attribute. Valid Values include "Yes" and "No".
        ================= ===============================================================================================================================================================

        """
        return self._groups

    @property
    def subgroups(self):
        """Returns a DataFrame for the group subgroups record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================== =================================================
        Column             Description
        ================== =================================================
        GPSGRP_RECORD_TYPE Record type of the Group Subgroups record (0101).
        GPSGRP_NAME        Group name as taken from the profile name.
        GPSGRP_SUBGRP_ID   The name of a subgroup within the group.
        ================== =================================================

        """
        return self._subgroups

    @property
    def connects(self):
        """Returns a DataFrame for the group members record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ================================================================================
        Column            Description
        ================= ================================================================================
        GPMEM_RECORD_TYPE Record type of the Group Members record (0102).
        GPMEM_NAME        Group name as taken from the profile name.
        GPMEM_MEMBER_ID   A user ID within the group.
        GPMEM_AUTH        Indicates the authority that the user ID has within the group. Valid values are 
        ================= ================================================================================

        """
        return self._connects

    @property
    def groupUSRDATA(self):
        """Returns a DataFrame for the group installation data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        =================== =========================================================
        Column              Description
        =================== =========================================================
        GPINSTD_RECORD_TYPE Record type of the Group Installation Data record (0103).
        GPINSTD_NAME        Group name as taken from the profile name.
        GPINSTD_USR_NAME    The name of the installation-defined field.
        GPINSTD_USR_DATA    The data for the installation-defined field.
        GPINSTD_USR_FLAG    The flag for the installation-defined field in the form 
        =================== =========================================================

        """
        return self._groupUSRDATA

    @property
    def groupDFP(self):
        """Returns a DataFrame for the group dfp data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ================================================
        Column            Description
        ================= ================================================
        GPDFP_RECORD_TYPE Record type of the Group DFP Data record (0110).
        GPDFP_NAME        Group name as taken from the profile name.
        GPDFP_DATAAPPL    Default application name for the group.
        GPDFP_DATACLAS    Default data class for the group.
        GPDFP_MGMTCLAS    Default management class for the group.
        GPDFP_STORCLAS    Default storage class for the group.
        ================= ================================================

        """
        return self._groupDFP

    @property
    def groupOMVS(self):
        """Returns a DataFrame for the group omvs data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================== =================================================
        Column             Description
        ================== =================================================
        GPOMVS_RECORD_TYPE Record type of the Group OMVS Data record (0120).
        GPOMVS_NAME        Group name as taken from the profile name.
        GPOMVS_GID         OMVS 
        ================== =================================================

        """
        return self._groupOMVS

    @property
    def groupOVM(self):
        """Returns a DataFrame for the group ovm data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ======================================================================================
        Column            Description
        ================= ======================================================================================
        GPOVM_RECORD_TYPE Record type of the Group OVM Data record (0130).
        GPOVM_NAME        Group name as taken from the profile name.
        GPOVM_GID         OpenExtensions group identifier (GID) associated with the group name from the profile.
        ================= ======================================================================================

        """
        return self._groupOVM

    @property
    def groupTME(self):
        """Returns a DataFrame for the group tme role record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ================================================
        Column            Description
        ================= ================================================
        GPTME_RECORD_TYPE Record type of the Group TME Data record (0141).
        GPTME_NAME        Group name as taken from the profile name.
        GPTME_ROLE        Role profile name.
        ================= ================================================

        """
        return self._groupTME

    @property
    def groupCSDATA(self):
        """Returns a DataFrame for the group csdata custom fields record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/format.htm

        ================= ======================================================================
        Column            Description
        ================= ======================================================================
        GPCSD_RECORD_TYPE Record type of the Group CSDATA custom fields (0151).
        GPCSD_NAME        Group name.
        GPCSD_TYPE        Data type for the custom field. Valid values are CHAR, FLAG, HEX, NUM.
        GPCSD_KEY         Custom field keyword; maximum length = 8.
        GPCSD_VALUE       Custom field value.
        ================= ======================================================================

        """
        return self._groupCSDATA

    @property
    def users(self):
        """Returns a DataFrame for the user basic data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        =================== ================================================================================================================================================================================================================================
        Column              Description
        =================== ================================================================================================================================================================================================================================
        USBD_RECORD_TYPE    Record type of the User Basic Data record (0200).
        USBD_NAME           User ID as taken from the profile name.
        USBD_CREATE_DATE    The date that the profile was created.
        USBD_OWNER_ID       The user ID or group name that owns the profile.
        USBD_ADSP           Does the user have the ADSP attribute? Valid Values include "Yes" and "No".
        USBD_SPECIAL        Does the user have the SPECIAL attribute? Valid Values include "Yes" and "No".
        USBD_OPER           Does the user have the OPERATIONS attribute? Valid Values include "Yes" and "No".
        USBD_REVOKE         Is the user REVOKEd? Valid Values include "Yes" and "No".
        USBD_GRPACC         Does the user have the GRPACC attribute? Valid Values include "Yes" and "No".
        USBD_PWD_INTERVAL   The number of days that the user's password can be used.
        USBD_PWD_DATE       The date that the password was last changed.
        USBD_PROGRAMMER     The name associated with the user ID.
        USBD_DEFGRP_ID      The default group associated with the user.
        USBD_LASTJOB_TIME   The last recorded time that the user entered the system.
        USBD_LASTJOB_DATE   The last recorded date that the user entered the system.
        USBD_INSTALL_DATA   Installation-defined data.
        USBD_UAUDIT         Do all RACHECK and RACDEF SVCs cause logging? Valid Values include "Yes" and "No".
        USBD_AUDITOR        Does this user have the AUDITOR attribute? Valid Values include "Yes" and "No".
        USBD_NOPWD          "YES" indicates that this user ID can log on without a password using OID card. "NO" indicates that this user must specify a password. "PRO" indicates a protected user ID. "PHR" indicates that the user has a password phrase.
        USBD_OIDCARD        Does this user have OIDCARD data? Valid Values include "Yes" and "No".
        USBD_PWD_GEN        The current password generation number.
        USBD_REVOKE_CNT     The number of unsuccessful logon attempts.
        USBD_MODEL          The data set model profile name.
        USBD_SECLEVEL       The user's security level.
        USBD_REVOKE_DATE    The date that the user is revoked.
        USBD_RESUME_DATE    The date that the user is resumed.
        USBD_ACCESS_SUN     Can the user access the system on Sunday? Valid Values include "Yes" and "No".
        USBD_ACCESS_MON     Can the user access the system on Monday? Valid Values include "Yes" and "No".
        USBD_ACCESS_TUE     Can the user access the system on Tuesday? Valid Values include "Yes" and "No".
        USBD_ACCESS_WED     Can the user access the system on Wednesday? Valid Values include "Yes" and "No".
        USBD_ACCESS_THU     Can the user access the system on Thursday? Valid Values include "Yes" and "No".
        USBD_ACCESS_FRI     Can the user access the system on Friday? Valid Values include "Yes" and "No".
        USBD_ACCESS_SAT     Can the user access the system on Saturday? Valid Values include "Yes" and "No".
        USBD_START_TIME     After what time can the user log on?
        USBD_END_TIME       After what time can the user not log on?
        USBD_SECLABEL       The user's default security label.
        USBD_ATTRIBS        Other user attributes (RSTD for users with RESTRICTED attribute).
        USBD_PWDENV_EXISTS  Has a PKCS#7 envelope been created for the user's current password? Valid Values include "Yes" and "No".
        USBD_PWD_ASIS       Should the password be evaluated in the case entered? Valid Values include "Yes" and "No".
        USBD_PHR_DATE       The date the password phrase was last changed.
        USBD_PHR_GEN        The current password phrase generation number.
        USBD_CERT_SEQN      Sequence number that is incremented whenever a certificate for the user is added, deleted, or altered. The starting value might not be 0.
        USBD_PPHENV_EXISTS  Has the user's current password phrase been PKCS#7 enveloped for possible retrieval? Valid Values include "Yes" and "No".
        USBD_PWD_ALG        Algorithm that is used to protect passwords.  Possible values are "LEGACY", "KDFAES", and "NOPASSWORD".
        USBD_LEG_PWDHIST_CT Number of legacy password history entries.
        USBD_XPW_PWDHIST_CT Number of KDFAES password history entries.
        USBD_PHR_ALG        Algorithm that is used to protect password phrases.  Possible values are "LEGACY", "KDFAES", and "NOPHRASE".
        USBD_LEG_PHRHIST_CT Number of legacy password phrase history entries.
        USBD_XPW_PHRHIST_CT Number of KDFAES password phrase history entries.
        USBD_ROAUDIT        This user can have a ROAUDIT attribute. Valid Values include "Yes" and "No".
        USBD_MFA_FALLBACK   This user can use a password or password phrase to logon to the system when MFA is unavailable. Valid Values include "Yes" and "No".
        USBD_PHR_INTERVAL   The number of days that the user's password phrase can be used.
        =================== ================================================================================================================================================================================================================================

        """
        return self._users

    @property
    def userCategories(self):
        """Returns a DataFrame for the user categories record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= =================================================
        Column            Description
        ================= =================================================
        USCAT_RECORD_TYPE Record type of the User Categories record (0201).
        USCAT_NAME        User ID as taken from the profile name.
        USCAT_CATEGORY    Category to which the user has access.
        ================= =================================================

        """
        return self._userCategories

    @property
    def userClasses(self):
        """Returns a DataFrame for the user classes record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ========================================================
        Column            Description
        ================= ========================================================
        USCLA_RECORD_TYPE Record type of the User Classes record (0202).
        USCLA_NAME        User ID as taken from the profile name.
        USCLA_CLASS       A class in which the user is allowed to define profiles.
        ================= ========================================================

        """
        return self._userClasses

    @property
    def groupConnect(self):
        """Returns a DataFrame for the user group connections record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ========================================================
        Column             Description
        ================== ========================================================
        USGCON_RECORD_TYPE Record type of the User Group Connections record (0203).
        USGCON_NAME        User ID as taken from the profile name.
        USGCON_GRP_ID      The group with which the user is associated.
        ================== ========================================================

        """
        return self._groupConnect

    @property
    def userUSRDATA(self):
        """Returns a DataFrame for the user installation data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        =================== ========================================================
        Column              Description
        =================== ========================================================
        USINSTD_RECORD_TYPE Record type of the User Installation Data record (0204).
        USINSTD_NAME        User ID as taken from the profile name.
        USINSTD_USR_NAME    The name of the installation-defined field.
        USINSTD_USR_DATA    The data for the installation-defined field.
        USINSTD_USR_FLAG    The flag for the installation-defined field in the form 
        =================== ========================================================

        """
        return self._userUSRDATA

    @property
    def connectData(self):
        """Returns a DataFrame for the user connect data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== =======================================================================================================================================
        Column             Description
        ================== =======================================================================================================================================
        USCON_RECORD_TYPE  Record type of the User Connect Data record (0205).
        USCON_NAME         User ID as taken from the profile name.
        USCON_GRP_ID       The group name.
        USCON_CONNECT_DATE The date that the user was connected.
        USCON_OWNER_ID     The owner of the user-group connection.
        USCON_LASTCON_TIME Time that the user last connected to this group.
        USCON_LASTCON_DATE Date that the user last connected to this group.
        USCON_UACC         The default universal access authority for all new resources the user defines while connected to the specified group. Valid values are 
        USCON_INIT_CNT     The number of RACINITs issued for this user/group combination.
        USCON_GRP_ADSP     Does this user have the ADSP attribute in this group? Valid Values include "Yes" and "No".
        USCON_GRP_SPECIAL  Does this user have GROUP-SPECIAL in this group? Valid Values include "Yes" and "No".
        USCON_GRP_OPER     Does this user have GROUP-OPERATIONS in this group? Valid Values include "Yes" and "No".
        USCON_REVOKE       Is this user revoked? Valid Values include "Yes" and "No".
        USCON_GRP_ACC      Does this user have the GRPACC attribute? Valid Values include "Yes" and "No".
        USCON_NOTERMUACC   Does this user have the NOTERMUACC attribute in this group? Valid Values include "Yes" and "No".
        USCON_GRP_AUDIT    Does this user have the GROUP-AUDITOR attribute in this group? Valid Values include "Yes" and "No".
        USCON_REVOKE_DATE  The date that the user's connection to the group is revoked.
        USCON_RESUME_DATE  The date that the user's connection to the group is resumed.
        ================== =======================================================================================================================================

        """
        return self._connectData

    @property
    def userRRSFdata(self):
        """Returns a DataFrame for the user rrsf data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ======================================================================================================
        Column             Description
        ================== ======================================================================================================
        USRSF_RECORD_TYPE  Record type of the RRSF data record (0206).
        USRSF_NAME         User ID as taken from the profile name.
        USRSF_TARG_NODE    Target node name.
        USRSF_TARG_USER_ID Target user ID.
        USRSF_VERSION      Version of this record.
        USRSF_PEER         Is this a peer user ID? Valid Values include "Yes" and "No".
        USRSF_MANAGING     Is USRSF_NAME managing this ID? Valid Values include "Yes" and "No".
        USRSF_MANAGED      Is USRSF_NAME being managed by this ID? Valid Values include "Yes" and "No".
        USRSF_REMOTE_PEND  Is this remote RACF association pending? Valid Values include "Yes" and "No".
        USRSF_LOCAL_PEND   Is this local RACF association pending? Valid Values include "Yes" and "No".
        USRSF_PWD_SYNC     Is there password synchronization with this user ID? Valid Values include "Yes" and "No".
        USRSF_REM_REFUSAL  Was a system error encountered on the remote system? Valid Values include "Yes" and "No".
        USRSF_DEFINE_DATE  GMT date stamp for when this record was defined.
        USRSF_DEFINE_TIME  GMT time stamp for when this record was defined.
        USRSF_ACCEPT_DATE  GMT date stamp when this association was approved or refused. Based on the REMOTE_REFUSAL bit setting.
        USRSF_ACCEPT_TIME  GMT time stamp when this association was approved or refused. Based on the REMOTE_REFUSAL bit setting.
        USRSF_CREATOR_ID   User ID who created this entry.
        ================== ======================================================================================================

        """
        return self._userRRSFdata

    @property
    def userCERTname(self):
        """Returns a DataFrame for the user certificate name record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== =======================================================
        Column             Description
        ================== =======================================================
        USCERT_RECORD_TYPE Record type of the user certificate name record (0207).
        USCERT_NAME        User ID as taken from the profile name.
        USCERT_CERT_NAME   Digital certificate name.
        USCERT_CERTLABL    Digital certificate label.
        ================== =======================================================

        """
        return self._userCERTname

    @property
    def userAssociationMapping(self):
        """Returns a DataFrame for the user associated mappings record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ===========================================================
        Column             Description
        ================== ===========================================================
        USNMAP_RECORD_TYPE Record type of the User Associated Mappings record (0208).
        USNMAP_NAME        User ID as taken from the profile name.
        USNMAP_LABEL       The label associated with this mapping.
        USNMAP_MAP_NAME    The name of the DIGTNMAP profile associated with this user.
        ================== ===========================================================

        """
        return self._userAssociationMapping

    @property
    def userDistributedIdMapping(self):
        """Returns a DataFrame for the user associated distributed mappings record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ======================================================================
        Column             Description
        ================== ======================================================================
        USDMAP_RECORD_TYPE Record type of the User Associated Distributed Mappings record (0209).
        USDMAP_NAME        User ID as taken from the profile name.
        USDMAP_LABEL       The label associated with this mapping.
        USDMAP_MAP_NAME    The name of the IDIDMAP profile associated with this user.
        ================== ======================================================================

        """
        return self._userDistributedIdMapping

    @property
    def userMFAfactor(self):
        """Returns a DataFrame for the user mfa factor data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        =================== ======================================================================
        Column              Description
        =================== ======================================================================
        USMFA_RECORD_TYPE   Record type of the user Multifactor authentication data record (020A).
        USMFA_NAME          User ID as taken from the profile name.
        USMFA_FACTOR_NAME   Factor name.
        USMFA_FACTOR_ACTIVE Factor active date. Will be blank if factor is not ACTIVE.
        =================== ======================================================================

        """
        return self._userMFAfactor

    @property
    def userMFApolicies(self):
        """Returns a DataFrame for the user mfa policies record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==========================================================================
        Column             Description
        ================== ==========================================================================
        USMPOL_RECORD_TYPE Record type of the user Multi-factor authentication policies record (020B)
        USMPOL_NAME        User ID as taken from the profile name.
        USMPOL_POLICY_NAME MFA Policy name.
        ================== ==========================================================================

        """
        return self._userMFApolicies

    @property
    def userDFP(self):
        """Returns a DataFrame for the user dfp data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ===============================================
        Column            Description
        ================= ===============================================
        USDFP_RECORD_TYPE Record type of the User DFP data record (0210).
        USDFP_NAME        User ID as taken from the profile name.
        USDFP_DATAAPPL    Default application name for the user.
        USDFP_DATACLAS    Default data class for the user.
        USDFP_MGMTCLAS    Default management class for the user.
        USDFP_STORCLAS    Default storage class for the user.
        ================= ===============================================

        """
        return self._userDFP

    @property
    def userTSO(self):
        """Returns a DataFrame for the user tso data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ===============================================
        Column             Description
        ================== ===============================================
        USTSO_RECORD_TYPE  Record type of the User TSO Data record (0220).
        USTSO_NAME         User ID as taken from the profile name.
        USTSO_ACCOUNT      The default account number.
        USTSO_COMMAND      The command issued at LOGON.
        USTSO_DEST         The default destination identifier.
        USTSO_HOLD_CLASS   The default hold class.
        USTSO_JOB_CLASS    The default job class.
        USTSO_LOGON_PROC   The default logon procedure.
        USTSO_LOGON_SIZE   The default logon region size.
        USTSO_MSG_CLASS    The default message class.
        USTSO_LOGON_MAX    The maximum logon region size.
        USTSO_PERF_GROUP   The performance group associated with the user.
        USTSO_SYSOUT_CLASS The default sysout class.
        USTSO_USER_DATA    The TSO user data, in hexadecimal in the form 
        USTSO_UNIT_NAME    The default SYSDA device.
        USTSO_SECLABEL     The default logon security label.
        ================== ===============================================

        """
        return self._userTSO

    @property
    def userCICS(self):
        """Returns a DataFrame for the user cics data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ======================================================================================================
        Column             Description
        ================== ======================================================================================================
        USCICS_RECORD_TYPE Record type of the User CICS Data record (0230).
        USCICS_NAME        User ID as taken from the profile name.
        USCICS_OPIDENT     The CICS operator identifier.
        USCICS_OPPRTY      The CICS operator priority.
        USCICS_NOFORCE     Is the extended recovery facility (XRF) NOFORCE option in effect? Valid Values include "Yes" and "No".
        USCICS_TIMEOUT     The terminal time-out value. Expressed in 
        ================== ======================================================================================================

        """
        return self._userCICS

    @property
    def userCICSoperatorClasses(self):
        """Returns a DataFrame for the user cics operator classes record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==========================================================
        Column             Description
        ================== ==========================================================
        USCOPC_RECORD_TYPE Record type of the User CICS Operator Class record (0231).
        USCOPC_NAME        User ID as taken from the profile name.
        USCOPC_OPCLASS     The class associated with the CICS operator.
        ================== ==========================================================

        """
        return self._userCICSoperatorClasses

    @property
    def userCICSrslKeys(self):
        """Returns a DataFrame for the user cics rsl keys record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ====================================================
        Column             Description
        ================== ====================================================
        USCRSL_RECORD_TYPE Record type of the User CICS RSL keys record (0232).
        USCRSL_NAME        User ID as taken from the profile name.
        USCRSL_KEY         RSL key number.
        ================== ====================================================

        """
        return self._userCICSrslKeys

    @property
    def userCICStslKeys(self):
        """Returns a DataFrame for the user cics tsl keys record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ====================================================
        Column             Description
        ================== ====================================================
        USCTSL_RECORD_TYPE Record type of the User CICS TSL keys record (0233).
        USCTSL_NAME        User ID as taken from the profile name.
        USCTSL_KEY         TSL key number.
        ================== ====================================================

        """
        return self._userCICStslKeys

    @property
    def userLANGUAGE(self):
        """Returns a DataFrame for the user language data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ====================================================
        Column            Description
        ================= ====================================================
        USLAN_RECORD_TYPE Record type of the User Language Data record (0240).
        USLAN_NAME        User ID as taken from the profile name.
        USLAN_PRIMARY     The primary language for the user.
        USLAN_SECONDARY   The secondary language for the user.
        ================= ====================================================

        """
        return self._userLANGUAGE

    @property
    def userOPERPARM(self):
        """Returns a DataFrame for the user operparm data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==========================================================================================================================================
        Column             Description
        ================== ==========================================================================================================================================
        USOPR_RECORD_TYPE  Record type of the User OPERPARM Data record (0250).
        USOPR_NAME         User ID as taken from the profile name.
        USOPR_STORAGE      The number of megabytes of storage that can be used for message queuing.
        USOPR_MASTERAUTH   Does this user have MASTER console authority? Valid Values include "Yes" and "No".
        USOPR_ALLAUTH      Does this user have ALL console authority? Valid Values include "Yes" and "No".
        USOPR_SYSAUTH      Does this user have SYSAUTH console authority? Valid Values include "Yes" and "No".
        USOPR_IOAUTH       Does this user have I/O console authority? Valid Values include "Yes" and "No".
        USOPR_CONSAUTH     Does this user have CONS console authority? Valid Values include "Yes" and "No".
        USOPR_INFOAUTH     Does this user have INFO console authority? Valid Values include "Yes" and "No".
        USOPR_TIMESTAMP    Do console messages contain a timestamp? Valid Values include "Yes" and "No".
        USOPR_SYSTEMID     Do console messages contain a system ID? Valid Values include "Yes" and "No".
        USOPR_JOBID        Do console messages contain a job ID? Valid Values include "Yes" and "No".
        USOPR_MSGID        Do console messages contain a message ID? Valid Values include "Yes" and "No".
        USOPR_X            Are the job name and system name to be suppressed for messages issued from the JES3 global processor? Valid Values include "Yes" and "No".
        USOPR_WTOR         Does the console receive WTOR messages? Valid Values include "Yes" and "No".
        USOPR_IMMEDIATE    Does the console receive 
        USOPR_CRITICAL     Does the console receive 
        USOPR_EVENTUAL     Does the console receive 
        USOPR_INFO         Does the console receive 
        USOPR_NOBRODCAST   Are broadcast messages to this console suppressed? Valid Values include "Yes" and "No".
        USOPR_ALL          Does the console receive 
        USOPR_JOBNAMES     Are job names monitored? Valid Values include "Yes" and "No".
        USOPR_JOBNAMEST    Are job names monitored with timestamps displayed? Valid Values include "Yes" and "No".
        USOPR_SESS         Are user IDs displayed with each TSO initiation and termination? Valid Values include "Yes" and "No".
        USOPR_SESST        Are user IDs and timestamps displayed with each TSO initiation and termination? Valid Values include "Yes" and "No".
        USOPR_STATUS       Are data set names and dispositions displayed with each data set that is freed? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE001 Is this console enabled for route code 001? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE002 Is this console enabled for route code 002? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE003 Is this console enabled for route code 003? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE004 Is this console enabled for route code 004? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE005 Is this console enabled for route code 005? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE006 Is this console enabled for route code 006? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE007 Is this console enabled for route code 007? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE008 Is this console enabled for route code 008? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE009 Is this console enabled for route code 009? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE010 Is this console enabled for route code 010? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE011 Is this console enabled for route code 011? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE012 Is this console enabled for route code 012? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE013 Is this console enabled for route code 013? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE014 Is this console enabled for route code 014? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE015 Is this console enabled for route code 015? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE016 Is this console enabled for route code 016? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE017 Is this console enabled for route code 017? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE018 Is this console enabled for route code 018? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE019 Is this console enabled for route code 019? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE020 Is this console enabled for route code 020? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE021 Is this console enabled for route code 021? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE022 Is this console enabled for route code 022? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE023 Is this console enabled for route code 023? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE024 Is this console enabled for route code 024? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE025 Is this console enabled for route code 025? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE026 Is this console enabled for route code 026? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE027 Is this console enabled for route code 027? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE028 Is this console enabled for route code 028? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE029 Is this console enabled for route code 029? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE030 Is this console enabled for route code 030? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE031 Is this console enabled for route code 031? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE032 Is this console enabled for route code 032? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE033 Is this console enabled for route code 033? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE034 Is this console enabled for route code 034? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE035 Is this console enabled for route code 035? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE036 Is this console enabled for route code 036? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE037 Is this console enabled for route code 037? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE038 Is this console enabled for route code 038? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE039 Is this console enabled for route code 039? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE040 Is this console enabled for route code 040? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE041 Is this console enabled for route code 041? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE042 Is this console enabled for route code 042? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE043 Is this console enabled for route code 043? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE044 Is this console enabled for route code 044? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE045 Is this console enabled for route code 045? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE046 Is this console enabled for route code 046? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE047 Is this console enabled for route code 047? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE048 Is this console enabled for route code 048? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE049 Is this console enabled for route code 049? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE050 Is this console enabled for route code 050? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE051 Is this console enabled for route code 051? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE052 Is this console enabled for route code 052? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE053 Is this console enabled for route code 053? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE054 Is this console enabled for route code 054? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE055 Is this console enabled for route code 055? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE056 Is this console enabled for route code 056? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE057 Is this console enabled for route code 057? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE058 Is this console enabled for route code 058? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE059 Is this console enabled for route code 059? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE060 Is this console enabled for route code 060? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE061 Is this console enabled for route code 061? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE062 Is this console enabled for route code 062? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE063 Is this console enabled for route code 063? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE064 Is this console enabled for route code 064? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE065 Is this console enabled for route code 065? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE066 Is this console enabled for route code 066? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE067 Is this console enabled for route code 067? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE068 Is this console enabled for route code 068? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE069 Is this console enabled for route code 069? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE070 Is this console enabled for route code 070? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE071 Is this console enabled for route code 071? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE072 Is this console enabled for route code 072? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE073 Is this console enabled for route code 073? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE074 Is this console enabled for route code 074? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE075 Is this console enabled for route code 075? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE076 Is this console enabled for route code 076? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE077 Is this console enabled for route code 077? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE078 Is this console enabled for route code 078? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE079 Is this console enabled for route code 079? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE080 Is this console enabled for route code 080? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE081 Is this console enabled for route code 081? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE082 Is this console enabled for route code 082? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE083 Is this console enabled for route code 083? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE084 Is this console enabled for route code 084? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE085 Is this console enabled for route code 085? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE086 Is this console enabled for route code 086? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE087 Is this console enabled for route code 087? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE088 Is this console enabled for route code 088? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE089 Is this console enabled for route code 089? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE090 Is this console enabled for route code 090? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE091 Is this console enabled for route code 091? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE092 Is this console enabled for route code 092? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE093 Is this console enabled for route code 093? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE094 Is this console enabled for route code 094? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE095 Is this console enabled for route code 095? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE096 Is this console enabled for route code 096? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE097 Is this console enabled for route code 097? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE098 Is this console enabled for route code 098? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE099 Is this console enabled for route code 099? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE100 Is this console enabled for route code 100? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE101 Is this console enabled for route code 101? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE102 Is this console enabled for route code 102? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE103 Is this console enabled for route code 103? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE104 Is this console enabled for route code 104? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE105 Is this console enabled for route code 105? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE106 Is this console enabled for route code 106? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE107 Is this console enabled for route code 107? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE108 Is this console enabled for route code 108? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE109 Is this console enabled for route code 109? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE110 Is this console enabled for route code 110? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE111 Is this console enabled for route code 111? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE112 Is this console enabled for route code 112? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE113 Is this console enabled for route code 113? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE114 Is this console enabled for route code 114? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE115 Is this console enabled for route code 115? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE116 Is this console enabled for route code 116? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE117 Is this console enabled for route code 117? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE118 Is this console enabled for route code 118? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE119 Is this console enabled for route code 119? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE120 Is this console enabled for route code 120? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE121 Is this console enabled for route code 121? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE122 Is this console enabled for route code 122? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE123 Is this console enabled for route code 123? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE124 Is this console enabled for route code 124? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE125 Is this console enabled for route code 125? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE126 Is this console enabled for route code 126? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE127 Is this console enabled for route code 127? Valid Values include "Yes" and "No".
        USOPR_ROUTECODE128 Is this console enabled for route code 128? Valid Values include "Yes" and "No".
        USOPR_LOGCMDRESP   Specifies the logging of command responses received by the extended operator. Valid values are 
        USOPR_MIGRATIONID  Is this extended operator to receive a migration ID?
        USOPR_DELOPERMSG   Does this extended operator receive delete operator messages? Valid values are 
        USOPR_RETRIEVE_KEY Specifies a retrieval key used for searching. A null value is indicated by 
        USOPR_CMDSYS       The name of the system that the extended operator is connected to for command processing.
        USOPR_UD           Is this operator to receive undeliverable messages? Valid Values include "Yes" and "No".
        USOPR_ALTGRP_ID    The default group associated with this operator.
        USOPR_AUTO         Is this operator to receive messages automated within the sysplex? Valid Values include "Yes" and "No".
        USOPR_HC           Is this operator to receive messages that are directed to hardcopy? Valid Values include "Yes" and "No".
        USOPR_INT          Is this operator to receive messages that are directed to console ID zero? Valid Values include "Yes" and "No".
        USOPR_UNKN         Is this operator to receive messages which are directed to unknown console IDs? Valid Values include "Yes" and "No".
        ================== ==========================================================================================================================================

        """
        return self._userOPERPARM

    @property
    def userOPERPARMscope(self):
        """Returns a DataFrame for the user operparm scope
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== =====================================================
        Column             Description
        ================== =====================================================
        USOPRP_RECORD_TYPE Record type of the User OPERPARM Scope record (0251).
        USOPRP_NAME        User ID as taken from the profile name.
        USOPRP_SYSTEM      System name.
        ================== =====================================================

        """
        return self._userOPERPARMscope

    @property
    def userWORKATTR(self):
        """Returns a DataFrame for the user workattr data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        =================== ====================================================
        Column              Description
        =================== ====================================================
        USWRK_RECORD_TYPE   Record type of the User WORKATTR Data record (0260).
        USWRK_NAME          User ID as taken from the profile name.
        USWRK_AREA_NAME     Area for delivery.
        USWRK_BUILDING      Building for delivery.
        USWRK_DEPARTMENT    Department for delivery.
        USWRK_ROOM          Room for delivery.
        USWRK_ADDR_LINE1    Address line 1.
        USWRK_ADDR_LINE2    Address line 2.
        USWRK_ADDR_LINE3    Address line 3.
        USWRK_ADDR_LINE4    Address line 4.
        USWRK_ACCOUNT       Account number.
        USWRK_EMAIL_ADDRESS E-mail address.
        =================== ====================================================

        """
        return self._userWORKATTR

    @property
    def userOMVS(self):
        """Returns a DataFrame for the user omvs data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ========================================================
        Column             Description
        ================== ========================================================
        USOMVS_RECORD_TYPE Record type of the User Data record (0270).
        USOMVS_NAME        User name as taken from the profile name.
        USOMVS_UID         z/OS UNIX
        USOMVS_HOME_PATH   HOME PATH associated with the 
        USOMVS_PROGRAM     Default Program associated with the 
        USOMVS_CPUTIMEMAX  Maximum CPU time associated with the UID.
        USOMVS_ASSIZEMAX   Maximum address space size associated with the UID.
        USOMVS_FILEPROCMAX Maximum active or open files associated with the UID.
        USOMVS_PROCUSERMAX Maximum number of processes associated with the UID.
        USOMVS_THREADSMAX  Maximum number of threads associated with the UID.
        USOMVS_MMAPAREAMAX Maximum mappable storage amount associated with the UID.
        USOMVS_MEMLIMIT    Maximum size of non-shared memory
        USOMVS_SHMEMAX     Maximum size of shared memory
        ================== ========================================================

        """
        return self._userOMVS

    @property
    def userNETVIEW(self):
        """Returns a DataFrame for the user netview segment record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== =======================================================================================
        Column             Description
        ================== =======================================================================================
        USNETV_RECORD_TYPE Record type of the user NETVIEW segment record (0280).
        USNETV_NAME        User ID as taken from profile name
        USNETV_IC          Command list processed at logon
        USNETV_CONSNAME    Default console name
        USNETV_CTL         CTL value: GENERAL, GLOBAL, or SPECIFIC
        USNETV_MSGRECVR    Eligible to receive unsolicited messages? Valid Values include "Yes" and "No".
        USNETV_NGMFADMN    Authorized to NetView graphic monitoring facility? Valid Values include "Yes" and "No".
        USNETV_NGMFVSPN    Value of view span options
        ================== =======================================================================================

        """
        return self._userNETVIEW

    @property
    def userNETVIEWopclass(self):
        """Returns a DataFrame for the user opclass record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==============================================
        Column             Description
        ================== ==============================================
        USNOPC_RECORD_TYPE Record type of the user OPCLASS record (0281).
        USNOPC_NAME        User ID as taken from the profile name
        USNOPC_OPCLASS     OPCLASS value from 1 to 2040
        ================== ==============================================

        """
        return self._userNETVIEWopclass

    @property
    def userNETVIEWdomains(self):
        """Returns a DataFrame for the user domains record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==============================================
        Column             Description
        ================== ==============================================
        USNDOM_RECORD_TYPE Record type of the user DOMAINS record (0282).
        USNDOM_NAME        User ID as taken from the profile name
        USNDOM_DOMAINS     DOMAIN value.
        ================== ==============================================

        """
        return self._userNETVIEWdomains

    @property
    def userDCE(self):
        """Returns a DataFrame for the user dce data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ======================================================================================
        Column            Description
        ================= ======================================================================================
        USDCE_RECORD_TYPE Record type of the user DCE data record (0290).
        USDCE_NAME        RACF user name as taken from the profile name.
        USDCE_UUID        DCE UUID associated with the user name from the profile.
        USDCE_DCE_NAME    DCE principal name associated with this user.
        USDCE_HOMECELL    Home cell name.
        USDCE_HOMEUUID    Home cell UUID.
        USDCE_AUTOLOGIN   Is this user eligible for an automatic DCE login? Valid Values include "Yes" and "No".
        ================= ======================================================================================

        """
        return self._userDCE

    @property
    def userOVM(self):
        """Returns a DataFrame for the user ovm data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= =====================================================================
        Column            Description
        ================= =====================================================================
        USOVM_RECORD_TYPE Record type of the user OVM data record (02A0).
        USOVM_NAME        User name as taken from the profile name.
        USOVM_UID         User identifier (UID) associated with the user name from the profile.
        USOVM_HOME_PATH   Home path associated with the user identifier (UID).
        USOVM_PROGRAM     Default program associated with the user identifier (UID).
        USOVM_FSROOT      File system root for this user.
        ================= =====================================================================

        """
        return self._userOVM

    @property
    def userLNOTES(self):
        """Returns a DataFrame for the user lnotes data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ==============================================
        Column             Description
        ================== ==============================================
        USLNOT_RECORD_TYPE Record type of the LNOTES data record (02B0).
        USLNOT_NAME        User ID as taken from the profile name.
        USLNOT_SNAME       LNOTES short name associated with the user ID.
        ================== ==============================================

        """
        return self._userLNOTES

    @property
    def userNDS(self):
        """Returns a DataFrame for the user nds data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ==========================================
        Column            Description
        ================= ==========================================
        USNDS_RECORD_TYPE Record type of the NDS data record (02C0).
        USNDS_NAME        User ID as taken from the profile name.
        USNDS_UNAME       NDS user name associated with the user ID.
        ================= ==========================================

        """
        return self._userNDS

    @property
    def userKERB(self):
        """Returns a DataFrame for the user kerb data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ====================== =========================================================================================
        Column                 Description
        ====================== =========================================================================================
        USKERB_RECORD_TYPE     Record type of the User KERB segment record (02D0).
        USKERB_NAME            RACF user name as taken from the profile.
        USKERB_KERBNAME        The Kerberos principal name.
        USKERB_MAX_LIFE        Maximum ticket life.
        USKERB_KEY_VERS        Current  key version.
        USKERB_ENCRYPT_DES     Is key encryption using DES enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRYPT_DES3    Is key encryption using DES3 enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRYPT_DESD    Is key encryption using DES with derivation enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRPT_A128     Is key encryption using AES128 enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRPT_A256     Is key encryption using AES256 enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRPT_A128SHA2 Is key encryption using AES128 SHA2 enabled? Valid Values include "Yes" and "No".
        USKERB_ENCRPT_A256SHA2 Is key encryption using AES256 SHA2 enabled? Valid Values include "Yes" and "No".
        USKERB_KEY_FROM        Key source. Valid values are PASSWORD or PHRASE.
        ====================== =========================================================================================

        """
        return self._userKERB

    @property
    def userPROXY(self):
        """Returns a DataFrame for the user proxy record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        =================== ==============================================
        Column              Description
        =================== ==============================================
        USPROXY_RECORD_TYPE Record type of the user PROXY record (02E0).
        USPROXY_NAME        RACF user name as taken from the profile name.
        USPROXY_LDAP_HOST   LDAP server URL.
        USPROXY_BIND_DN     LDAP BIND distinguished name.
        =================== ==============================================

        """
        return self._userPROXY

    @property
    def userEIM(self):
        """Returns a DataFrame for the user eim data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ==================================================
        Column            Description
        ================= ==================================================
        USEIM_RECORD_TYPE Record type of the user EIM segment record (02F0).
        USEIM_NAME        User name.
        USEIM_LDAPPROF    EIM LDAPBIND profile name.
        ================= ==================================================

        """
        return self._userEIM

    @property
    def userCSDATA(self):
        """Returns a DataFrame for the user csdata custom fields record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================= ======================================================================
        Column            Description
        ================= ======================================================================
        USCSD_RECORD_TYPE Record type of the user CSDATA custom fields record (02G1).
        USCSD_NAME        User name.
        USCSD_TYPE        Data type for the custom field. Valid values are CHAR, FLAG, HEX, NUM.
        USCSD_KEY         Custom field keyword; maximum length = 8.
        USCSD_VALUE       Custom field value.
        ================= ======================================================================

        """
        return self._userCSDATA

    @property
    def userMFAfactorTags(self):
        """Returns a DataFrame for the user mfa factor tags data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/usr.htm

        ================== ===========================================================================================
        Column             Description
        ================== ===========================================================================================
        USMFAC_RECORD_TYPE Record type of the user Multifactor authentication factor configuration data record (1210).
        USMFAC_NAME        User ID as taken from the profile name.
        USMFAC_FACTOR_NAME Factor name.
        USMFAC_TAG_NAME    The tag name associated with the factor.
        USMFAC_TAG_VALUE   Tag value associated with the tag name.
        ================== ===========================================================================================

        """
        return self._userMFAfactorTags

    @property
    def datasets(self):
        """Returns a DataFrame for the data set basic data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================== =============================================================================================
        Column             Description
        ================== =============================================================================================
        DSBD_RECORD_TYPE   Record type of the Data Set Basic Data record (0400).
        DSBD_NAME          Data set name as taken from the profile name.
        DSBD_VOL           Volume upon which this data set resides. Blank if the profile is generic, and 
        DSBD_GENERIC       Is this a generic profile?
        DSBD_CREATE_DATE   Date the profile was created.
        DSBD_OWNER_ID      The user ID or group name that owns the profile.
        DSBD_LASTREF_DATE  The date that the data set was last referenced.
        DSBD_LASTCHG_DATE  The date that the data set was last changed.
        DSBD_ALTER_CNT     The number of times that the data set was accessed with ALTER authority.
        DSBD_CONTROL_CNT   The number of times that the data set was accessed with CONTROL authority.
        DSBD_UPDATE_CNT    The number of times that the data set was accessed with UPDATE authority.
        DSBD_READ_CNT      The number of times that the data set was accessed with READ authority.
        DSBD_UACC          The universal access of this data set. Valid values are 
        DSBD_GRPDS         Is this a group data set?
        DSBD_AUDIT_LEVEL   Indicates the level of resource-owner-specified auditing that is performed. Valid values are 
        DSBD_GRP_ID        The connect group of the user who created this data set.
        DSBD_DS_TYPE       The type of the data set. Valid values are 
        DSBD_LEVEL         The level of the data set.
        DSBD_DEVICE_NAME   The EBCDIC name of the device type on which the data set resides.
        DSBD_GAUDIT_LEVEL  Indicates the level of auditor-specified auditing that is performed. Valid values are 
        DSBD_INSTALL_DATA  Installation-defined data.
        DSBD_AUDIT_OKQUAL  The resource-owner-specified successful access audit qualifier. This is set to blanks if 
        DSBD_AUDIT_FAQUAL  The resource-owner-specified failing access audit qualifier. This is set to blanks if 
        DSBD_GAUDIT_OKQUAL The auditor-specified successful access audit qualifier. This is set to blanks if 
        DSBD_GAUDIT_FAQUAL The auditor-specified failing access audit qualifier. This is set to blanks if 
        DSBD_WARNING       Does this data set have the WARNING attribute?
        DSBD_SECLEVEL      The data set security level.
        DSBD_NOTIFY_ID     User ID that is notified when violations occur.
        DSBD_RETENTION     Retention period of the data set.
        DSBD_ERASE         For a DASD data set, is this data set scratched when the data set is deleted?
        DSBD_SECLABEL      Security label of the data set.
        DSBD_RESERVED_01   Reserved
        DSBD_RESERVED_02   Reserved
        ================== =============================================================================================

        """
        return self._datasets

    @property
    def datasetCategories(self):
        """Returns a DataFrame for the data set categories record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ==============================================================================
        Column            Description
        ================= ==============================================================================
        DSCAT_RECORD_TYPE Record type of the Data Set Categories record (0401).
        DSCAT_NAME        Data set name as taken from the profile name.
        DSCAT_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSCAT_CATEGORY    Category associated with this data set.
        ================= ==============================================================================

        """
        return self._datasetCategories

    @property
    def datasetConditionalAccess(self):
        """Returns a DataFrame for the data set conditional access record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================== ==================================================================================
        Column             Description
        ================== ==================================================================================
        DSCACC_RECORD_TYPE Record type of the Data Set Conditional Access record (0402).
        DSCACC_NAME        Data set name as taken from the profile name.
        DSCACC_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSCACC_CATYPE      The type of conditional access checking that is being performed. Valid values are 
        DSCACC_CANAME      The name of a conditional access element that is permitted access.
        DSCACC_AUTH_ID     The user ID or group name that is authorized to the data set.
        DSCACC_ACCESS      The access of the conditional access element/user combination. Valid values are 
        DSCACC_ACCESS_CNT  The number of times that the data set was accessed.
        DSCACC_NET_ID      The network name when DSCACC_CATYPE is APPCPORT.
        DSCACC_CACRITERIA  The IP name when DSCACC_CATYPE is SERVAUTH.
        ================== ==================================================================================

        """
        return self._datasetConditionalAccess

    @property
    def datasetVolumes(self):
        """Returns a DataFrame for the data set volumes record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ==================================================
        Column            Description
        ================= ==================================================
        DSVOL_RECORD_TYPE Record type of the Data Set Volumes record (0403).
        DSVOL_NAME        Data set name as taken from the profile name.
        DSVOL_VOL         Volume upon which this data set resides.
        DSVOL_VOL_NAME    A volume upon which the data set resides.
        ================= ==================================================

        """
        return self._datasetVolumes

    @property
    def datasetAccess(self):
        """Returns a DataFrame for the data set access record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ==============================================================================
        Column            Description
        ================= ==============================================================================
        DSACC_RECORD_TYPE Record type of the Data Set Access Record (0404).
        DSACC_NAME        Data set name as taken from the profile name.
        DSACC_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSACC_AUTH_ID     The user ID or group name that is authorized to the data set.
        DSACC_ACCESS      The access allowed to the user. Valid values are 
        DSACC_ACCESS_CNT  The number of times that the data set was accessed.
        ================= ==============================================================================

        """
        return self._datasetAccess

    @property
    def datasetUSRDATA(self):
        """Returns a DataFrame for the data set installation data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        =================== ==============================================================================
        Column              Description
        =================== ==============================================================================
        DSINSTD_RECORD_TYPE Record type of the Data Set Installation Data Record (0405).
        DSINSTD_NAME        Data set name as taken from the profile name.
        DSINSTD_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSINSTD_USR_NAME    The name of the installation-defined field.
        DSINSTD_USR_DATA    The data for the installation-defined field.
        DSINSTD_USR_FLAG    The flag for the installation-defined field in the form 
        =================== ==============================================================================

        """
        return self._datasetUSRDATA

    @property
    def datasetMember(self):
        """Returns a DataFrame for the data set member record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ===============================================================================================
        Column            Description
        ================= ===============================================================================================
        DSMEM_RECORD_TYPE Record type of the Data Set Member Data Record (0406).
        DSMEM_NAME        Data set name as taken from the profile name.
        DSMEM_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSMEM_MEMBER_NAME Member name.
        DSMEM_AUTH_ID     The user ID or group name that is authorized to the member.
        DSMEM_ACCESS      The access that is allowed to the ID. Valid values are "NONE", "READ", "UPDATE", and "CONTROL".
        ================= ===============================================================================================

        """
        return self._datasetMember

    @property
    def datasetDFP(self):
        """Returns a DataFrame for the data set dfp data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ===========================================================================================
        Column            Description
        ================= ===========================================================================================
        DSDFP_RECORD_TYPE Record type of the Data Set DFP Data record (0410).
        DSDFP_NAME        Data set name as taken from the profile name.
        DSDFP_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSDFP_RESOWNER_ID The resource owner of the data set.
        DSDFP_DATAKEY     The label of the ICSF key that is used to encrypt the data of any newly allocated data set.
        ================= ===========================================================================================

        """
        return self._datasetDFP

    @property
    def datasetTME(self):
        """Returns a DataFrame for the data set tme role record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= ==============================================================================
        Column            Description
        ================= ==============================================================================
        DSTME_RECORD_TYPE Record type of the Data Set TME Data Record (0421).
        DSTME_NAME        Data set name as taken from the profile name.
        DSTME_VOL         Volume upon which this data set resides. Blank if the profile is generic, and 
        DSTME_ROLE_NAME   Role profile name.
        DSTME_ACCESS_AUTH Access permission to this resource as defined by the role.
        DSTME_COND_CLASS  Class name for conditional access.
        DSTME_COND_PROF   Resource profile for conditional access.
        ================= ==============================================================================

        """
        return self._datasetTME

    @property
    def datasetCSDATA(self):
        """Returns a DataFrame for the data set csdata record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/dsr.htm

        ================= =======================================================================================================================
        Column            Description
        ================= =======================================================================================================================
        DSCSD_RECORD_TYPE Record type of the Data Set CSDATA custom fields record (0431).
        DSCSD_NAME        Data set name as taken from the profile name.
        DSCSD_VOL         Volume upon which this data set resides. Blank if the profile is generic, and \*MODEL if the profile is a model profile.
        DSCSD_TYPE        Data type for the custom field. Valid values are CHAR, FLAG, HEX, NUM.
        DSCSD_KEY         Custom field keyword; maximum length = 8.
        DSCSD_VALUE       Custom field value.
        ================= =======================================================================================================================

        """
        return self._datasetCSDATA

    @property
    def generals(self):
        """Returns a DataFrame for the general resource basic data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== =========================================================================================================================
        Column             Description
        ================== =========================================================================================================================
        GRBD_RECORD_TYPE   Record type of the General Resource Basic Data record (0500).
        GRBD_NAME          General resource name as taken from the profile name.
        GRBD_CLASS_NAME    Name of the class to which the general resource profile belongs.
        GRBD_GENERIC       Is this a generic profile? Valid Values include "Yes" and "No".
        GRBD_CLASS         The class number of the profile.
        GRBD_CREATE_DATE   Date the profile was created.
        GRBD_OWNER_ID      The user ID or group name which owns the profile.
        GRBD_LASTREF_DATE  The date that the resource was last referenced.
        GRBD_LASTCHG_DATE  The date that the resource was last changed.
        GRBD_ALTER_CNT     The number of times that the resource was accessed with ALTER authority.
        GRBD_CONTROL_CNT   The number of times that the resource was accessed with CONTROL authority.
        GRBD_UPDATE_CNT    The number of times that the resource was accessed with UPDATE authority.
        GRBD_READ_CNT      The number of times that the resource was accessed with READ authority.
        GRBD_UACC          The universal access of this resource. For profiles in classes other than DIGTCERT, the valid values are 
        GRBD_AUDIT_LEVEL   Indicates the level of resource-owner-specified auditing that is performed. Valid values are 
        GRBD_LEVEL         The level of the resource.
        GRBD_GAUDIT_LEVEL  Indicates the level of auditor-specified auditing that is performed. Valid values are 
        GRBD_INSTALL_DATA  Installation-defined data.
        GRBD_AUDIT_OKQUAL  The resource-owner-specified successful access audit qualifier. This is set to blanks if 
        GRBD_AUDIT_FAQUAL  The resource-owner-specified failing access audit qualifier. This is set to blanks if 
        GRBD_GAUDIT_OKQUAL The auditor-specified successful access audit qualifier. This is set to blanks if 
        GRBD_GAUDIT_FAQUAL The auditor-specified failing access audit qualifier. This is set to blanks if 
        GRBD_WARNING       Does this resource have the WARNING attribute? Valid Values include "Yes" and "No".
        GRBD_SINGLEDS      If this is a TAPEVOL profile, is there only one data set on this tape? Valid Values include "Yes" and "No".
        GRBD_AUTO          If this is a TAPEVOL profile, is the TAPEVOL protection automatic? Valid Values include "Yes" and "No".
        GRBD_TVTOC         If this is a TAPEVOL profile, is there a tape volume table of contents on this tape? Valid Values include "Yes" and "No".
        GRBD_NOTIFY_ID     User ID that is notified when violations occur.
        GRBD_ACCESS_SUN    Can the terminal be used on Sunday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_MON    Can the terminal be used on Monday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_TUE    Can the terminal be used on Tuesday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_WED    Can the terminal be used on Wednesday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_THU    Can the terminal be used on Thursday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_FRI    Can the terminal be used on Friday? Valid Values include "Yes" and "No".
        GRBD_ACCESS_SAT    Can the terminal be used on Saturday? Valid Values include "Yes" and "No".
        GRBD_START_TIME    After what time can a user logon from this terminal?
        GRBD_END_TIME      After what time can a user not logon from this terminal?
        GRBD_ZONE_OFFSET   Time zone in which the terminal is located. Expressed as 
        GRBD_ZONE_DIRECT   The direction of the time zone shift. Valid values are 
        GRBD_SECLEVEL      The security level of the general resource.
        GRBD_APPL_DATA     Installation-defined data.
        GRBD_SECLABEL      The security label for the general resource.
        ================== =========================================================================================================================

        """
        return self._generals

    @property
    def generalTAPEvolume(self):
        """Returns a DataFrame for the general resource tape volume data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ========================================================================
        Column             Description
        ================== ========================================================================
        GRTVOL_RECORD_TYPE Record type of the General Resource Tape Volume Data record (0501).
        GRTVOL_NAME        General resource name as taken from the profile name.
        GRTVOL_CLASS_NAME  Name of the class to which the general resource profile belongs, namely 
        GRTVOL_SEQUENCE    The file sequence number of the tape data set.
        GRTVOL_CREATE_DATE Creation date of the tape data set.
        GRTVOL_DISCRETE    Does a discrete profile exist? Valid Values include "Yes" and "No".
        GRTVOL_INTERN_NAME The RACF internal data set name.
        GRTVOL_INTERN_VOLS The volumes upon which the data set resides.
        GRTVOL_CREATE_NAME The data set name used when creating the data set.
        ================== ========================================================================

        """
        return self._generalTAPEvolume

    @property
    def generalCategories(self):
        """Returns a DataFrame for the general resource categories record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ================================================================
        Column            Description
        ================= ================================================================
        GRCAT_RECORD_TYPE Record type of the General Resources Categories record (0502).
        GRCAT_NAME        General resource name as taken from the profile name.
        GRCAT_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCAT_CATEGORY    Category to which this general resource belongs.
        ================= ================================================================

        """
        return self._generalCategories

    @property
    def generalMembers(self):
        """Returns a DataFrame for the general resource members record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ======================================================================================================================================
        Column             Description
        ================== ======================================================================================================================================
        GRMEM_RECORD_TYPE  Record type of the General Resource Members record (0503).
        GRMEM_NAME         General resource name as taken from the profile name.
        GRMEM_CLASS_NAME   Name of the class to which the general resource profile belongs.
        GRMEM_MEMBER       Member value for this general resource. 
        GRMEM_GLOBAL_ACC   If this is a 
        GRMEM_PADS_DATA    If this is a PROGRAM profile, this field contains the Program Access to Data Set (PADS) information for the profile. Valid values are 
        GRMEM_VOL_NAME     If this is a PROGRAM profile, this field defines the volume upon which the program resides.
        GRMEM_VMEVENT_DATA If this is a VMXEVENT profile, this field defines the level of auditing that is being performed. Valid values are 
        GRMEM_SECLEVEL     If this is a SECLEVEL profile in the SECDATA class, this is the numeric security level that is associated with the SECLEVEL.
        GRMEM_CATEGORY     If this is a CATEGORY profile in the SECDATA class, this is the numeric category that is associated with the CATEGORY.
        ================== ======================================================================================================================================

        """
        return self._generalMembers

    @property
    def generalTAPEvolumes(self):
        """Returns a DataFrame for the general resource volumes record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ========================================================================
        Column            Description
        ================= ========================================================================
        GRVOL_RECORD_TYPE Record type of the General Resources Volumes record (0504).
        GRVOL_NAME        General resource name as taken from the profile name.
        GRVOL_CLASS_NAME  Name of the class to which the general resource profile belongs, namely 
        GRVOL_VOL_NAME    Name of a volume in a tape volume set.
        ================= ========================================================================

        """
        return self._generalTAPEvolumes

    @property
    def generalAccess(self):
        """Returns a DataFrame for the general resource access record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= =============================================================================
        Column            Description
        ================= =============================================================================
        GRACC_RECORD_TYPE Record type of the General Resource Access record (0505).
        GRACC_NAME        General resource name as taken from the profile name.
        GRACC_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRACC_AUTH_ID     User ID or group name which is authorized to use the general resource.
        GRACC_ACCESS      The authority that the user or group has over the resource. Valid values are 
        GRACC_ACCESS_CNT  The number of times that the resource was accessed.
        ================= =============================================================================

        """
        return self._generalAccess

    @property
    def generalUSRDATA(self):
        """Returns a DataFrame for the general resource installation data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        =================== ====================================================================
        Column              Description
        =================== ====================================================================
        GRINSTD_RECORD_TYPE Record type of the General Resource Installation Data record (0506).
        GRINSTD_NAME        General resource name as taken from the profile name.
        GRINSTD_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRINSTD_USR_NAME    The name of the installation-defined field.
        GRINSTD_USR_DATA    The data for the installation-defined field.
        GRINSTD_USR_FLAG    The flag for the installation-defined field in the form 
        =================== ====================================================================

        """
        return self._generalUSRDATA

    @property
    def generalConditionalAccess(self):
        """Returns a DataFrame for the general resource conditional access record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ===================================================================================
        Column             Description
        ================== ===================================================================================
        GRCACC_RECORD_TYPE Record type of the General Resources Conditional Access record (0507).
        GRCACC_NAME        General resource name as taken from the profile name.
        GRCACC_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCACC_CATYPE      The type of conditional access checking that is being performed. Valid values are 
        GRCACC_CANAME      The name of a conditional access element which is permitted access.
        GRCACC_AUTH_ID     The user ID or group name which has authority to the general resource.
        GRCACC_ACCESS      The authority of the conditional access element/user combination. Valid values are 
        GRCACC_ACCESS_CNT  The number of times that the general resource was accessed.
        GRCACC_NET_ID      The network name when GRCACC_CATYPE is APPCPORT.
        GRCACC_CACRITERIA  Access criteria or SERVAUTH IP data.
        ================== ===================================================================================

        """
        return self._generalConditionalAccess

    @property
    def generalDistributedIdFilter(self):
        """Returns a DataFrame for the general resource filter data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ======================================================================
        Column             Description
        ================== ======================================================================
        GRFLTR_RECORD_TYPE Record Type of the Filter Data record (0508).
        GRFLTR_NAME        General resource name as taken from the profile name.
        GRFLTR_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRFLTR_LABEL       The label associated with this filter.
        GRFLTR_STATUS      The status of this filter (TRUST) for filters that are trusted.
        GRFLTR_USER        The user ID or criteria profile name associated with this filter.
        GRFLTR_CREATE_NAME The issuer's or subject's name, or both, used to create this profile. 
        ================== ======================================================================

        """
        return self._generalDistributedIdFilter

    @property
    def generalDistributedIdMapping(self):
        """Returns a DataFrame for the general resource distributed identity mapping data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ====================================================================================
        Column             Description
        ================== ====================================================================================
        GRDMAP_RECORD_TYPE Record Type of the General Resource Distributed Identity Mapping Data record (0509).
        GRDMAP_NAME        General resource name as taken from the profile name.
        GRDMAP_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRDMAP_LABEL       The label associated with this mapping.
        GRDMAP_USER        The RACF user ID associated with this mapping.
        GRDMAP_DIDREG      The registry name value associated with this mapping.
        ================== ====================================================================================

        """
        return self._generalDistributedIdMapping

    @property
    def generalSESSION(self):
        """Returns a DataFrame for the general resource session data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ==========================================================================================
        Column             Description
        ================== ==========================================================================================
        GRSES_RECORD_TYPE  Record type of the General Resources Session Data record (0510).
        GRSES_NAME         General resource name as taken from the profile name.
        GRSES_CLASS_NAME   Name of the class to which the general resource profile belongs, namely 
        GRSES_SESSION_KEY  The key associated with the APPC session.
        GRSES_LOCKED       Is the profile locked? Valid Values include "Yes" and "No".
        GRSES_KEY_DATE     Last date that the session key was changed.
        GRSES_KEY_INTERVAL Number of days that the key is valid.
        GRSES_SLS_FAIL     Current  number of failed attempts.
        GRSES_MAX_FAIL     Number of failed attempts before lockout.
        GRSES_CONVSEC      Specifies the security checking performed when sessions are established. Valid values are 
        ================== ==========================================================================================

        """
        return self._generalSESSION

    @property
    def generalSESSIONentities(self):
        """Returns a DataFrame for the general resource session entities record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ========================================================================
        Column             Description
        ================== ========================================================================
        GRSESE_RECORD_TYPE Record type of the General Resources Session Entities record (0511).
        GRSESE_NAME        General resource name as taken from the profile name.
        GRSESE_CLASS_NAME  Name of the class to which the general resource profile belongs, namely 
        GRSESE_ENTITY_NAME Entity name.
        GRSESE_FAIL_CNT    The number of failed session attempts.
        ================== ========================================================================

        """
        return self._generalSESSIONentities

    @property
    def generalDLFDATA(self):
        """Returns a DataFrame for the general resource dlf data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ========================================================================
        Column            Description
        ================= ========================================================================
        GRDLF_RECORD_TYPE Record type of the General Resources DLF Data record (0520).
        GRDLF_NAME        General resource name as taken from the profile name.
        GRDLF_CLASS_NAME  Name of the class to which the general resource profile belongs, namely 
        GRDLF_RETAIN      Is this a retained resource? Valid Values include "Yes" and "No".
        ================= ========================================================================

        """
        return self._generalDLFDATA

    @property
    def generalDLFDATAjobnames(self):
        """Returns a DataFrame for the general resource dlf job names record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ========================================================================
        Column             Description
        ================== ========================================================================
        GRDLFJ_RECORD_TYPE Record type of the General Resources DLF Job Names record (0521).
        GRDLFJ_NAME        General resource name as taken from the profile name.
        GRDLFJ_CLASS_NAME  Name of the class to which the general resource profile belongs, namely 
        GRDLFJ_JOB_NAME    The job name associated with the general resource.
        ================== ========================================================================

        """
        return self._generalDLFDATAjobnames

    @property
    def generalSSIGNON(self):
        """Returns a DataFrame for the general resource ssignon data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ================================================================
        Column             Description
        ================== ================================================================
        GRSIGN_RECORD_TYPE Record type of the SSIGNON data record (0530).
        GRSIGN_NAME        General resource name as taken from the profile name.
        GRSIGN_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRSIGN_PROTECTION   
        GRSIGN_KEY_LABEL   The enhanced PassTicket ICSF CKDS Key Label name.
        GRSIGN_TYPE        Enhanced PassTicket type.
        GRSIGN_TIMEOUT     Enhanced PassTicket timeout setting.
        GRSIGN_REPLAY      Indicates whether enhanced PassTicket replays are allowed.
        ================== ================================================================

        """
        return self._generalSSIGNON

    @property
    def generalSTDATA(self):
        """Returns a DataFrame for the general resource started task data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================ ==================================================================
        Column           Description
        ================ ==================================================================
        GRST_RECORD_TYPE Record type (0540).
        GRST_NAME        Profile name.
        GRST_CLASS_NAME  The class name, STARTED.
        GRST_USER_ID     User ID assigned.
        GRST_GROUP_ID    Group name assigned.
        GRST_TRUSTED     Is process to run trusted? Valid Values include "Yes" and "No".
        GRST_PRIVILEGED  Is process to run privileged? Valid Values include "Yes" and "No".
        GRST_TRACE       Is entry to be traced? Valid Values include "Yes" and "No".
        ================ ==================================================================

        """
        return self._generalSTDATA

    @property
    def generalSVFMR(self):
        """Returns a DataFrame for the general resource systemview data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================ ========================================
        Column           Description
        ================ ========================================
        GRSV_RECORD_TYPE Record type (0550).
        GRSV_NAME        Profile name.
        GRSV_CLASS_NAME  Class name, SYSMVIEW.
        GRSV_SCRIPT_NAME Logon script name for the application.
        GRSV_PARM_NAME   Parameter list name for the application.
        ================ ========================================

        """
        return self._generalSVFMR

    @property
    def generalCERT(self):
        """Returns a DataFrame for the general resource certificate data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ==============================================================================================================================
        Column             Description
        ================== ==============================================================================================================================
        GRCERT_RECORD_TYPE Record type of the Certificate Data record (0560).
        GRCERT_NAME        General resource name as taken from the profile name.
        GRCERT_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCERT_START_DATE  The date from which this certificate is valid.
        GRCERT_START_TIME  The time from which this certificate is valid.
        GRCERT_END_DATE    The date after which this certificate is no longer valid.
        GRCERT_END_TIME    The time after which this certificate is no longer valid.
        GRCERT_KEY_TYPE    The type of key associated with the certificate. Valid values: 
        GRCERT_KEY_SIZE    The size of private key associated with the certificate, expressed in bits.
        GRCERT_LAST_SERIAL The hexadecimal representation of the low-order eight bytes of the serial number of the last certificate signed with this key.
        GRCERT_RING_SEQN   A sequence number for certificates within the ring.
        GRCERT_GEN_REQ     Indicator to show if the certificate is used to generate a request. Valid Values include "Yes" and "No".
        ================== ==============================================================================================================================

        """
        return self._generalCERT

    @property
    def generalCERTreferences(self):
        """Returns a DataFrame for the general resource certificate references record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ==============================================================================================
        Column            Description
        ================= ==============================================================================================
        CERTR_RECORD_TYPE Record type of the Certificate References record (0561).
        CERTR_NAME        General resource name as taken from the profile name.
        CERTR_CLASS_NAME  Name of the class to which the general resource profile belongs.
        CERTR_RING_NAME   The name of the profile which represents a key ring with which this certificate is associated.
        ================= ==============================================================================================

        """
        return self._generalCERTreferences

    @property
    def generalKEYRING(self):
        """Returns a DataFrame for the general resource key ring data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= =================================================================================================
        Column            Description
        ================= =================================================================================================
        KEYR_RECORD_TYPE  Record type of the Key Ring Data record (0562).
        KEYR_NAME         General resource name as taken from the profile name.
        KEYR_CLASS_NAME   Name of the class to which the general resource profile belongs.
        KEYR_CERT_NAME    The name of the profile which contains the certificate which is in this key ring.
        KEYR_CERT_USAGE   The usage of the certificate within the ring. Valid values are 
        KEYR_CERT_DEFAULT Is this certificate the default certificate within the ring? Valid Values include "Yes" and "No".
        KEYR_CERT_LABEL   The label associated with the certificate.
        ================= =================================================================================================

        """
        return self._generalKEYRING

    @property
    def generalTME(self):
        """Returns a DataFrame for the general resource tme data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ===========================================================
        Column            Description
        ================= ===========================================================
        GRTME_RECORD_TYPE Record type of the general resource TME data record (0570).
        GRTME_NAME        General resource name as taken from the profile name.
        GRTME_CLASS_NAME  Name of the class to which the general resource belongs.
        GRTME_PARENT      Parent role.
        ================= ===========================================================

        """
        return self._generalTME

    @property
    def generalTMEchild(self):
        """Returns a DataFrame for the general resource tme child record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ============================================================
        Column             Description
        ================== ============================================================
        GRTMEC_RECORD_TYPE Record type of the general resource TME child record (0571).
        GRTMEC_NAME        General resource name as taken from the profile name.
        GRTMEC_CLASS_NAME  Name of the class to which the general resource belongs.
        GRTMEC_CHILD       Child role.
        ================== ============================================================

        """
        return self._generalTMEchild

    @property
    def generalTMEresource(self):
        """Returns a DataFrame for the general resource tme resource record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ===============================================================
        Column             Description
        ================== ===============================================================
        GRTMER_RECORD_TYPE Record type of the general resource TME resource record (0572).
        GRTMER_NAME        General resource name as taken from the profile name.
        GRTMER_CLASS_NAME  Name of the class to which the general resource belongs.
        GRTMER_ORIGIN_ROLE Role profile from which resource access is inherited.
        GRTMER_PROF_CLASS  Class name of the origin-role resource.
        GRTMER_PROF_NAME   Resource name defined in the origin role.
        GRTMER_ACCESS_AUTH Access permission to the resource.
        GRTMER_COND_CLASS  Class name for conditional access.
        GRTMER_COND_PROF   Resource profile for conditional access.
        ================== ===============================================================

        """
        return self._generalTMEresource

    @property
    def generalTMEgroup(self):
        """Returns a DataFrame for the general resource tme group record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ============================================================
        Column             Description
        ================== ============================================================
        GRTMEG_RECORD_TYPE Record type of the general resource TME group record (0573).
        GRTMEG_NAME        General resource name as taken from the profile name.
        GRTMEG_CLASS_NAME  Name of the class to which the general resource belongs.
        GRTMEG_GROUP       Group name defined to the role.
        ================== ============================================================

        """
        return self._generalTMEgroup

    @property
    def generalTMErole(self):
        """Returns a DataFrame for the general resource tme role record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ===========================================================
        Column             Description
        ================== ===========================================================
        GRTMEE_RECORD_TYPE Record type of the general resource TME role record (0574).
        GRTMEE_NAME        General resource name as taken from the profile name.
        GRTMEE_CLASS_NAME  Name of the class to which the general resource belongs.
        GRTMEE_ROLE_NAME   Role profile name.
        GRTMEE_ACCESS_AUTH Access permission to this resource as defined by the role.
        GRTMEE_COND_CLASS  Class name for conditional access.
        GRTMEE_COND_PROF   Resource profile for conditional access.
        ================== ===========================================================

        """
        return self._generalTMErole

    @property
    def generalKERB(self):
        """Returns a DataFrame for the general resource kerb data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ====================== ===========================================================================================
        Column                 Description
        ====================== ===========================================================================================
        GRKERB_RECORD_TYPE     Record type of the general resource KERB segment record (0580).
        GRKERB_NAME            General resource name as taken from the profile name.
        GRKERB_CLASS_NAME      Name of the class to which the general resource profile belongs.
        GRKERB_KERBNAME        The Kerberos realm name.
        GRKERB_MIN_LIFE        Minimum ticket life.
        GRKERB_MAX_LIFE        Maximum ticket life.
        GRKERB_DEF_LIFE        Default ticket life.
        GRKERB_KEY_VERS        Current key version.
        GRKERB_ENCRYPT_DES     Is key encryption using DES enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRYPT_DES3    Is key encryption using DES3 enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRYPT_DESD    Is key encryption using DES with derivation enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRPT_A128     Is key encryption using AES128 enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRPT_A256     Is key encryption using AES256 enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRPT_A128SHA2 Is key encryption using AES128 SHA2 enabled? Valid Values include "Yes" and "No".
        GRKERB_ENCRPT_A256SHA2 Is key encryption using AES256 SHA2 enabled? Valid Values include "Yes" and "No".
        GRKERB_CHKADDRS        Should the Kerberos server check addresses in tickets? Valid Values include "Yes" and "No".
        ====================== ===========================================================================================

        """
        return self._generalKERB

    @property
    def generalPROXY(self):
        """Returns a DataFrame for the general resource proxy record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        =================== ========================================================
        Column              Description
        =================== ========================================================
        GRPROXY_RECORD_TYPE Record type of the general resource PROXY record (0590).
        GRPROXY_NAME        General resource name as taken from the profile name.
        GRPROXY_CLASS_NAME  Name of the class to which the general resource belongs.
        GRPROXY_LDAP_HOST   LDAP server URL.
        GRPROXY_BIND_DN     LDAP BIND distinguished name.
        =================== ========================================================

        """
        return self._generalPROXY

    @property
    def generalEIM(self):
        """Returns a DataFrame for the general resource eim record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ==============================================================
        Column            Description
        ================= ==============================================================
        GREIM_RECORD_TYPE Record type of the general resource EIM segment record (05A0).
        GREIM_NAME        Profile name.
        GREIM_CLASS_NAME  Class name.
        GREIM_DOMAIN_DN   EIM domain name.
        GREIM_ENABLE      EIM Enable option. Valid Values include "Yes" and "No".
        RESERVED          Reserved for IBM's use.
        GREIM_LOCAL_REG   EIM LDAP local registry name.
        GREIM_KERBREG     EIM Kerberos Registry Name
        GREIM_X509REG     EIM X.509 Registry name
        ================= ==============================================================

        """
        return self._generalEIM

    @property
    def generalALIAS(self):
        """Returns a DataFrame for the general resource alias data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        =================== ==============================================================
        Column              Description
        =================== ==============================================================
        GRALIAS_RECORD_TYPE Record type of the general resource ALIAS group record (05B0).
        GRALIAS_NAME        General resource name as taken from the profile.
        GRALIAS_CLASS_NAME  Name of the class to which the general resource belongs.
        GRALIAS_IPLOOK      IP lookup value in SERVAUTH class.
        =================== ==============================================================

        """
        return self._generalALIAS

    @property
    def generalCDTINFO(self):
        """Returns a DataFrame for the general resource cdtinfo data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== =================================================================================================================
        Column             Description
        ================== =================================================================================================================
        GRCDT_RECORD_TYPE  Record type of the general resource CDTINFO data record (05C0).
        GRCDT_NAME         General resource name as taken from the profile.
        GRCDT_CLASS_NAME   Name of the class to which the general resource belongs, namely 
        GRCDT_POSIT        POSIT number for class.
        GRCDT_MAXLENGTH    Maximum length of profile names when using ENTITYX.
        GRCDT_MAXLENX      Maximum length of profile names when using ENTITYX.
        GRCDT_DEFAULTRC    Default return code.
        GRCDT_KEYQUALIFIER Number of key qualifiers.
        GRCDT_GROUP        Resource grouping class name.
        GRCDT_MEMBER       Member class name.
        GRCDT_FIRST_ALPHA  Is an alphabetic character allowed in the first character of a profile name? Valid Values include "Yes" and "No".
        GRCDT_FIRST_NATL   Is a national character allowed in the first character of a profile name? Valid Values include "Yes" and "No".
        GRCDT_FIRST_NUM    Is a numeric character allowed in the first character of a profile name? Valid Values include "Yes" and "No".
        GRCDT_FIRST_SPEC   Is a special character allowed in the first character of a profile name? Valid Values include "Yes" and "No".
        GRCDT_OTHER_ALPHA  Is an alphabetic character allowed in other characters of a profile name? Valid Values include "Yes" and "No".
        GRCDT_OTHER_NATL   Is a national character allowed in other characters of a profile name? Valid Values include "Yes" and "No".
        GRCDT_OTHER_NUM    Is a numeric character allowed in other characters of a profile name? Valid Values include "Yes" and "No".
        GRCDT_OTHER_SPEC   Is a special character allowed in other characters of a profile name? Valid Values include "Yes" and "No".
        GRCDT_OPER         Is OPERATIONS attribute to be considered? Valid Values include "Yes" and "No".
        GRCDT_DEFAULTUACC  Default universal access. Valid values are 
        GRCDT_RACLIST      RACLIST setting. Valid values are 
        GRCDT_GENLIST      GENLIST setting. Valid values are 
        GRCDT_PROF_ALLOW   Are profiles allowed in the class? Valid Values include "Yes" and "No".
        GRCDT_SECL_REQ     Are security labels required for the class when MLACTIVE is on? Valid Values include "Yes" and "No".
        GRCDT_MACPROCESS   Type of mandatory access check processing. Valid values are 
        GRCDT_SIGNAL       Is ENF signal to be sent? Valid Values include "Yes" and "No".
        GRCDT_CASE         Case of profile names. Valid values are 
        GRCDT_GENERIC      GENERIC setting. Valid values are ALLOWED and DISALLOWED.
        ================== =================================================================================================================

        """
        return self._generalCDTINFO

    @property
    def generalICTX(self):
        """Returns a DataFrame for the general resource ictx data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ==============================================================================================================
        Column             Description
        ================== ==============================================================================================================
        GRICTX_RECORD_TYPE Record type of the general resource ICTX segment record (05D0).
        GRICTX_NAME        General resource name as taken from the profile name.
        GRICTX_CLASS_NAME  Name of the class to which the general resource profile belongs. 
        GRICTX_USEMAP      Should the identity cache store an application provided identity mapping? Valid Values include "Yes" and "No".
        GRICTX_DOMAP       Should the identity cache determine and store the identity mapping? Valid Values include "Yes" and "No".
        GRICTX_MAPREQ      Is an identity mapping required? Valid Values include "Yes" and "No".
        GRICTX_MAP_TIMEOUT How long the identity cache should store an identity mapping.
        ================== ==============================================================================================================

        """
        return self._generalICTX

    @property
    def generalCFDEF(self):
        """Returns a DataFrame for the general resource cfdef data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        =================== =============================================================================================================================
        Column              Description
        =================== =============================================================================================================================
        GRCFDEF_RECORD_TYPE Record type of the general resource CFDEF data record (05E0).
        GRCFDEF_NAME        General resource name as taken from the profile name.
        GRCFDEF_CLASS       Name of the class to which the general resource belongs, namely CFIELD.
        GRCFDEF_TYPE        Data type for the custom field. Valid values are CHAR, FLAG, HEX, NUM.
        GRCFDEF_MAXLEN      Maximum length of the custom field.
        GRCFDEF_MAXVAL      Maximum value of the custom field.
        GRCFDEF_MINVAL      Minimum value of the custom field.
        GRCFDEF_FIRST       Character restriction for the first character. Valid values are ALPHA, ALPHANUM, ANY, NONATABC, NONATNUM, NUMERIC.
        GRCFDEF_OTHER       Character restriction for other characters. Valid values are ALPHA, ALPHANUM, ANY, NONATABC, NONATNUM, NUMERIC.
        GRCFDEF_MIXED       Is mixed case allowed in the field? Valid values are "Yes" and "No".
        GRCFDEF_HELP        Help text for the custom field.
        GRCFDEF_LISTHEAD    List heading for the custom field.
        GRCFDEF_VALREXX     Name of the REXX exec to validate the custom field value.
        GRCFDEF_ACEE        For USER profile fields, is this field to be made available in an ACEE created for the user? Valid values are "Yes" and "No".
        =================== =============================================================================================================================

        """
        return self._generalCFDEF

    @property
    def generalSIGVER(self):
        """Returns a DataFrame for the general resource sigver data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ===================================================================================================
        Column            Description
        ================= ===================================================================================================
        GRSIG_RECORD_TYPE Record type of the general resource SIGVER data record (05F0).
        GRSIG_NAME        General resource name as taken from the profile name.
        GRSIG_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRSIG_SIGREQUIRED Signature required. Valid Values include "Yes" and "No".
        GRSIG_FAILLOAD    Condition for which load should fail. Valid values are NEVER, BADSIGONLY, and ANYBAD.
        GRSIG_AUDIT       Condition for which RACF should audit. Valid values are NONE, ALL, SUCCESS, BADSIGONLY, and ANYBAD.
        ================= ===================================================================================================

        """
        return self._generalSIGVER

    @property
    def generalICSF(self):
        """Returns a DataFrame for the general resource icsf record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ======================================================================================================================================================================
        Column            Description
        ================= ======================================================================================================================================================================
        GRCSF_RECORD_TYPE Record type of the general resource ICSF record (05G0).
        GRCSF_NAME        General resource name as taken from the profile name.
        GRCSF_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCSF_EXPORTABLE  Is the symmetric key exportable? Valid values are: BYNONE, BYLIST, and BYANY.
        GRCSF_USAGE       Allowable uses of the asymmetric key. Valid values are: HANDSHAKE, NOHANDSHAKE, SECUREEXPORT, and NOSECUREEXPORT.
        GRCSF_CPACF_WRAP  Specifies whether the encrypted symmetric key is eligible to be rewrapped by CP Assist for Cryptographic Function (CPACF). Valid Values include "Yes" and "No".
        GRCSF_CPACF_RET   Specifies whether the encrypted symmetric keys that are rewrapped by CP Assist for Cryptographic Function (CPACF) are eligible to be returned to an authorized caller.
        ================= ======================================================================================================================================================================

        """
        return self._generalICSF

    @property
    def generalICSFsymexportKeylabel(self):
        """Returns a DataFrame for the general resource icsf key label record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== =============================================================================
        Column             Description
        ================== =============================================================================
        GRCSFK_RECORD_TYPE Record type of the general resource ICSF key label record (05G1).
        GRCSFK_NAME        General resource name as taken from the profile name.
        GRCSFK_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCSFK_LABEL       ICSF key label of a public key that can be used to export this symmetric key.
        ================== =============================================================================

        """
        return self._generalICSFsymexportKeylabel

    @property
    def generalICSFsymexportCertificateIdentifier(self):
        """Returns a DataFrame for the general resource icsf certificate identifier record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== =====================================================================================
        Column             Description
        ================== =====================================================================================
        GRCSFC_RECORD_TYPE Record type of the general resource ICSF certificate identifier record (05G2).
        GRCSFC_NAME        General resource name as taken from the profile name.
        GRCSFC_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCSFC_LABEL       Certificate identifier of a public key that can be used to export this symmetric key.
        ================== =====================================================================================

        """
        return self._generalICSFsymexportCertificateIdentifier

    @property
    def generalMFA(self):
        """Returns a DataFrame for the general resource mfa factor definition record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ===================== ===============================================================================
        Column                Description
        ===================== ===============================================================================
        GRMFA_RECORD_TYPE     Record type of the Multifactor factor definition data record (05H0)
        GRMFA_NAME            General resource name as taken from the profile name.
        GRMFA_CLASS_NAME      Name of the class to which the general resource profile belongs, namely MFADEF.
        GRMFA_FACTOR_DATA_LEN Length of factor data.
        ===================== ===============================================================================

        """
        return self._generalMFA

    @property
    def generalMFPOLICY(self):
        """Returns a DataFrame for the general resource mfpolicy definition record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        =================== ===============================================================================
        Column              Description
        =================== ===============================================================================
        GRMFP_RECORD_TYPE   Record type of the Multifactor Policy Definition data record (05I0).
        GRMFP_NAME          General resource name as taken from the profile name.
        GRMFP_CLASS_NAME    Name of the class to which the general resource profile belongs, namely MFADEF.
        GRMFP_TOKEN_TIMEOUT MFA token timeout setting.
        GRMFP_REUSE         MFA token reuse setting.
        =================== ===============================================================================

        """
        return self._generalMFPOLICY

    @property
    def generalMFPOLICYfactors(self):
        """Returns a DataFrame for the general resource mfa policy factors record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ================================================================================
        Column            Description
        ================= ================================================================================
        GRMPF_RECORD_TYPE Record type of the user Multifactor authentication policy factors record (05I1).
        GRMPF_NAME        General resource name as taken from the profile name.
        GRMPF_CLASS_NAME  Name of the class to which the general resource profile belongs, namely MFADEF.
        GRMPF_POL_FACTOR  Policy factor name.
        ================= ================================================================================

        """
        return self._generalMFPOLICYfactors

    @property
    def generalCSDATA(self):
        """Returns a DataFrame for the general resource csdata record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= ======================================================================
        Column            Description
        ================= ======================================================================
        GRCSD_RECORD_TYPE Record type of the General Resources CSDA custom fields record (05J1).
        GRCSD_NAME        General resource name as taken from the profile name.
        GRCSD_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRCSD_TYPE        Data type for the custom field. Valid values are CHAR, FLAG, HEX, NUM.
        GRCSD_KEY         Custom field keyword; maximum length = 8.
        GRCSD_VALUE       Custom field value.
        ================= ======================================================================

        """
        return self._generalCSDATA

    @property
    def generalIDTFPARMS(self):
        """Returns a DataFrame for the general resource idtparms definition record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ===================== =========================================================================================
        Column                Description
        ===================== =========================================================================================
        GRIDTP_RECORD_TYPE    Record type of the Identity Token data record (05K0).
        GRIDTP_NAME           General resource name as taken from the profile name.
        GRIDTP_CLASS_NAME     Name of the class to which the general resource profile belongs, namely IDTDATA.
        GRIDTP_SIG_TOKEN_NAME The ICSF PKCS#11 token name.
        GRIDTP_SIG_SEQ_NUM    The ICSF PKCS#11 sequence number.
        GRIDTP_SIG_CAT        The ICSF PKCS#11 category.
        GRIDTP_SIG_ALG        The signature algorithm.
        GRIDTP_TIMEOUT        IDT timeout setting.
        GRIDTP_ANYAPPL        Is the IDT allowed for any application? Valid values include "Yes" and "No".
        GRIDTP_PROTALLOWED    Is the IDT allowed to authenticate a protected user? Valid values include “Yes” and “No”.
        ===================== =========================================================================================

        """
        return self._generalIDTFPARMS

    @property
    def generalJES(self):
        """Returns a DataFrame for the general resource jes data record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================= =====================================================================
        Column            Description
        ================= =====================================================================
        GRJES_RECORD_TYPE Record type of the JES data record (05L0).
        GRJES_NAME        General resource name as taken from the profile name.
        GRJES_CLASS_NAME  Name of the class to which the general resource profile belongs.
        GRJES_KEYLABEL    The label of the ICSF key that is used to encrypt the JES spool data.
        ================= =====================================================================

        """
        return self._generalJES

    @property
    def generalCERTname(self):
        """Returns a DataFrame for the general resource certificate information record
        More information: https://www.ibm.com/docs/en/SSLTBW_3.1.0/com.ibm.zos.v3r1.icha300/grr.htm

        ================== ===========================================================================================================================================================================================================
        Column             Description
        ================== ===========================================================================================================================================================================================================
        CERTN_RECORD_TYPE  Record type of the general resource certificate information record (1560).
        CERTN_NAME         General resource name as taken from the profile name.
        CERTN_CLASS_NAME   Name of the class to which the general resource profile belongs.
        CERTN_ISSUER_DN    Issuers distinguished name.
        CERTN_SUBJECT_DN   Subjects distinguished name.
        CERTN_SIG_ALG      Certificate signature algorithm. Valid values are md2RSA, md5RSA, sha1RSA, sha1DSA, sha256RSA, sha224RSA, sha384RSA, sha512RSA, sha1ECDSA, sha256ECDSA, sha224ECDSA, sha384ECDSA, sha512ECDSA, and UNKNOWN.
        CERTN_CERT_FGRPRNT Certificate SHA256 fingerprint in printable hex.
        ================== ===========================================================================================================================================================================================================

        """
        return self._generalCERTname

