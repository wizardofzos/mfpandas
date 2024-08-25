import os 
import pandas as pd 
import datetime 

import threading
import time

class UsageError(Exception):
    """Raised when a usage error occurs."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class DCOLLECT:

    """
    This class contains code to parse a DCOLLECT dataset.

    After parsing you get a Pandas DataFrame for every recordtype from the DCOLLECT data. 

    To create a DCOLLECT dataset on z/OS amend and execute the following JCL::

            //STEP00 EXEC  PGM=IDCAMS                       
            //SYSPRINT DD  SYSOUT=*                        
            //MCDS     DD  DSN=PATH.TO.MCDS,     
            //             DISP=SHR                        
            //BCDS     DD  DSN=PATH.TO.BCDS,       
            //             DISP=SHR                        
            //DCOUT    DD  DSN=YOUR.DCOLLECT.FILE,               
            //             DISP=(NEW,CATLG),               
            //             SPACE=(CYL,(10,1),RLSE),        
            //             DCB=(RECFM=VB,BLKSIZE=27998),   
            //             UNIT=SYSDA                      
            //SYSIN    DD  *                               
                DCOLLECT -                                
                    OUTFILE(DCOUT) -                    
                    MIGRATEDATA -                       
                    CAPPLANDATA -                       
                    BACKUPDATA -                        
                    SMSDATA(SCDSNAME(ACTIVE)) -         
                    VOLUME(*)         
            
    Then, transfer "YOUR.DCOLLECT.FILE" to your machine. Make sure this is a BINARY transfer
   

    Args:
        dcollect (str): The full path to your DCOLLECT file. Defaults
            to None.
    """
    # Our states
    STATE_BAD         = -1
    STATE_INIT        =  0
    STATE_PARSING     =  1
    STATE_READY       =  2

    # Counters
    records_seen = {}
    records_parsed = {}

    def __init__(self, dcollect=None):
        """
        Initialize the DCOLLECT class.
        Recordlayout from: https://www.ibm.com/docs/en/zos/3.1.0?topic=output-dcollect-record-structure

        Recordtypes supported: D (Datasets), V (Volumes).

        :param dcollect: Full path to DCOLLECT file
        :type dcollect: str
        :raise UsageError: If no dcollect file specified.

        Example usage::

            >>> from mfpandas import DCOLLECT
            >>> d = DCOLLECT(dcollect='/path/to/binary/dcollect/file')         




        """
        if not dcollect:
            raise UsageError("No DCOLLECT file specified.")
        self._dcolfile = dcollect

        self._state = self.STATE_INIT 

        self._DRECS = {
            'DCDDSNAM': [],
            'DCDRACFD': [],
            'DCDSMSM': [],
            'DCDTEMP': [], 
            'DCDPDSE': [], 
            'DCDGDS': [],  
            'DCDREBLK': [],
            'DCDCHIND': [],
            'DCDCKDSI': [],
            'DCDNOVVR': [],
            'DCDINTCG': [],
            'DCDINICF': [],
            'DCDALLFG': [],
            'DCDUSEFG': [],
            'DCDSECFG': [],
            'DCDNMBFG': [],
            'DCDPDSEX': [],
            'DCDSTRP': [],
            'DCDDDMEX': [],
            'DCDCPOIT': [],
            'DCDGT64K': [],
            'DCDCMPTV': [],
            'DCDDSGIS': [],
            'DCDDSGPS': [],
            'DCDDSGDA': [],
            'DCDDSGPO': [],
            'DCDDSGU': [],
            'DCDDSGGS': [],
            'DCDDSGVS': [],
            'DCDRECFF': [],
            'DCDRECFV': [],
            'DCDRECFU': [],
            'DCDRECFT': [],
            'DCDRECFB': [],
            'DCDRECFS': [],
            'DCDRECFA': [],
            'DCDRECFC': [],
            'DCDNMEXT': [],
            'DCDVOLSR': [],
            'DCDBKLNG': [],
            'DCDLRECL': [],
            'DCDALLSP': [],
            'DCDUSESP': [],
            'DCDSCALL': [],    
            'DCDNMBLK': [],
            'DCDCREDT': [],
            'DCDEXPDT': [],
            'DCDLSTRF': [],
            'DCDATCL': [],
            'DCDSTGCL': [],
            'DCDMGTCL': [],
            'DCDSTGRP': []
            }
        self._VRECS = {
            'DCVVOLSR': [],
            'DCVPERCT': [],
            'DCVFRESP': [],
            'DCVALLOC': [],
            'DCVVLCAP': [],
            'DCVFRAGI': [],
            'DCVLGEXT': [],
            'DCVFREXT': [],
            'DCVFDSCB': [],
            'DCVFVIRS': [],
            'DCVDVTYP': [],
            'DCVDVNUM': [],
            'DCVSGTCL': [],
            'DCVDPTYP': [],

        }                   

    def parse_t(self):
        """
        Function to parse the dcollect file.
        This function is called inside a thread via the parse() function.

        Example usage::

            >>> from mfpandas import DCOLLECT
            >>> d = DCOLLECT(dcollect='/path/to/binary/dcollect/file') 
            >>> d.parse_t()        

        """
        with open(self._dcolfile, 'rb') as fid:
            self._state = self.STATE_PARSING
            while True:
                try:
                    DCULENG = int(fid.read(2).hex(),16)
                except:
                    # we must have hit the end of the file :)
                    break
                #print('Have a record of',DCULENG,'bytes')
                restrec = fid.read(DCULENG-2)
                DCURCTYP = restrec[2:4].decode('cp500').strip()
                if DCURCTYP in self.records_seen:
                    self.records_seen[DCURCTYP] += 1
                else:
                    self.records_seen[DCURCTYP] = 1
                    self.records_parsed[DCURCTYP] = 0
                if DCURCTYP == 'D':
                    self._DRECS['DCDDSNAM'].append(restrec[22:66].decode('cp500').strip())
                    DCDERROR = bin(restrec[66])
                    DCDFLAG1 = int(bin(restrec[67]),2)
                    self._DRECS['DCDRACFD'].append((DCDFLAG1 & 0b10000000) != 0)
                    self._DRECS['DCDSMSM'].append((DCDFLAG1 & 0b01000000) != 0)
                    self._DRECS['DCDTEMP'].append((DCDFLAG1 & 0b00100000) != 0)
                    self._DRECS['DCDPDSE'].append((DCDFLAG1 & 0b00010000) != 0)
                    self._DRECS['DCDGDS'].append((DCDFLAG1 & 0b00001000) != 0)
                    self._DRECS['DCDREBLK'].append((DCDFLAG1 & 0b00000100) != 0)
                    self._DRECS['DCDCHIND'].append((DCDFLAG1 & 0b00000010) != 0)
                    self._DRECS['DCDCKDSI'].append((DCDFLAG1 & 0b00000001) != 0)

                    DCDFLAG2 = int(bin(restrec[68]),2)
                    self._DRECS['DCDNOVVR'].append((DCDFLAG2 & 0b10000000) != 0)
                    self._DRECS['DCDINTCG'].append((DCDFLAG2 & 0b01000000) != 0)
                    self._DRECS['DCDINICF'].append((DCDFLAG2 & 0b00100000) != 0)
                    if (DCDFLAG2 & 0b00001000) != 0:
                        # 31 BIT SPACE ALLOCATED TO DATA SET IN KBs (1024). ONLY VALID WHEN DCDALLFG = ON.
                        self._DRECS['DCDALLSP'].append((int(restrec[86:90].hex(),16)))
                    else:
                        self._DRECS['DCDALLSP'].append(0)
                    self._DRECS['DCDALLFG'].append((DCDFLAG2 & 0b00001000) != 0)
                    if (DCDFLAG2 & 0b00000100) != 0:
                        # 31 BIT SPACE USED BY DATA SET IN KBs (1024). ONLY VALID WHEN DCDUSEFG = ON.
                        self._DRECS['DCDUSESP'].append((int(restrec[90:94].hex(),16)))
                    else:
                        self._DRECS['DCDUSESP'].append(0)
                    self._DRECS['DCDUSEFG'].append((DCDFLAG2 & 0b00000100) != 0)
                    if (DCDFLAG2 & 0b00000010) != 0:
                        #31 BIT SECONDARY ALLOCATION IN KBs (1024). ONLY VALID WHEN DCDSECFG = ON.
                        self._DRECS['DCDSCALL'].append((int(restrec[94:98].hex(),16)))
                    else:
                         self._DRECS['DCDSCALL'].append(0)
                    self._DRECS['DCDSECFG'].append((DCDFLAG2 & 0b00000010) != 0)
                    if (DCDFLAG2 & 0b00000001) != 0:
                        #31 BIT NUMBER OF KILOBYTES (1024) THAT COULD BE ADDED TO THE USED SPACE IF THE BLOCK SIZE OR CI SIZE WERE OPTIMIZED. ONLY VALID WHEN DCDNMBFG = ON.
                        self._DRECS['DCDNMBLK'].append((int(restrec[98:102].hex(),16)))
                    else:
                        self._DRECS['DCDNMBLK'].append(0)
                    self._DRECS['DCDNMBFG'].append((DCDFLAG2 & 0b00000001) != 0)
    
                    DCDFLAG3 = int(bin(restrec[69]),2)
                    self._DRECS['DCDPDSEX'].append((DCDFLAG3 & 0b10000000) != 0)
                    self._DRECS['DCDSTRP'].append((DCDFLAG3 & 0b01000000) != 0)
                    self._DRECS['DCDDDMEX'].append((DCDFLAG3 & 0b00100000) != 0)
                    self._DRECS['DCDCPOIT'].append((DCDFLAG3 & 0b00010000) != 0)
                    self._DRECS['DCDGT64K'].append((DCDFLAG3 & 0b00001000) != 0)
                    self._DRECS['DCDCMPTV'].append((DCDFLAG3 & 0b00000100) != 0)
         
                    DCDDSOR0 = int(bin(restrec[72]),2)
                    self._DRECS['DCDDSGIS'].append((DCDDSOR0 & 0b10000000) != 0)
                    self._DRECS['DCDDSGPS'].append((DCDDSOR0 & 0b01000000) != 0)
                    self._DRECS['DCDDSGDA'].append((DCDDSOR0 & 0b00100000) != 0)
                    self._DRECS['DCDDSGPO'].append((DCDDSOR0 & 0b00000010) != 0)
                    self._DRECS['DCDDSGU'].append((DCDDSOR0 & 0b00000001) != 0)

                    DCDDSOR1 = int(bin(restrec[73]),2)
                    self._DRECS['DCDDSGGS'].append((DCDDSOR1 & 0b10000000) != 0)
                    self._DRECS['DCDDSGVS'].append((DCDDSOR1 & 0b00001000) != 0)

                    DCDRECRD = int(bin(restrec[74]),2)
                    self._DRECS['DCDRECFF'].append((DCDRECRD & 0b10000000) != 0)
                    self._DRECS['DCDRECFV'].append((DCDRECRD & 0b01000000) != 0)
                    self._DRECS['DCDRECFU'].append((DCDRECRD & 0b11000000) != 0)
                    self._DRECS['DCDRECFT'].append((DCDRECRD & 0b00100000) != 0)
                    self._DRECS['DCDRECFB'].append((DCDRECRD & 0b00010000) != 0)      
                    self._DRECS['DCDRECFS'].append((DCDRECRD & 0b00001000) != 0) 
                    self._DRECS['DCDRECFA'].append((DCDRECRD & 0b00000100) != 0) 
                    self._DRECS['DCDRECFC'].append((DCDRECRD & 0b00000010) != 0)                                  

                    self._DRECS['DCDNMEXT'].append(int(restrec[75]))
                    self._DRECS['DCDVOLSR'].append(restrec[76:82].decode('cp500'))
                    self._DRECS['DCDBKLNG'].append(int(restrec[82:84].hex(),16))
                    self._DRECS['DCDLRECL'].append(int(restrec[84:86].hex(),16))

                    # formats = yyyydddF
                    createraw = restrec[102:106].hex()[0:7]
                    crdte = datetime.datetime.strptime(createraw, '%Y%j').date()
                    self._DRECS['DCDCREDT'].append(crdte)

                    expraw = restrec[106:110].hex()[0:7]
                    if expraw == '0000000':
                        expdte = False
                    elif expraw[4:] == '000':
                        expdte = False 
                    else:
                        try:
                            expdte =  datetime.datetime.strptime(expraw, '%Y%j').date()
                        except:
                            # https://www.mxg.com/changes/chng0808.asp
                            expdte = False
                    
                    self._DRECS['DCDEXPDT'].append(expdte)

                    lrraw = restrec[110:114].hex()[0:7]
                    if lrraw == '0000000':
                        lrdte = False
                    else:
                        lrdte = datetime.datetime.strptime(lrraw, '%Y%j').date()
                    self._DRECS['DCDLSTRF'].append(lrdte)



                    dc = restrec[132:162].decode('cp500').strip()
                    sc = restrec[164:194].decode('cp500').strip()
                    mc = restrec[196:226].decode('cp500').strip()
                    sg = restrec[228:258].decode('cp500').strip()

                    if dc != '':
                        self._DRECS['DCDATCL'].append(dc)
                    else:
                        self._DRECS['DCDATCL'].append('*NONE*')
                    
                    if sc != '':
                        self._DRECS['DCDSTGCL'].append(sc)
                    else:
                        self._DRECS['DCDSTGCL'].append('*NONE*')
                    
                    if mc != '':
                        self._DRECS['DCDMGTCL'].append(mc)
                    else:
                        self._DRECS['DCDMGTCL'].append('*NONE*')

                    if sg != '':
                        self._DRECS['DCDSTGRP'].append(sg)
                    else:
                        self._DRECS['DCDSTGRP'].append('*NONE*')

                    
                    self.records_parsed['D'] += 1
                elif DCURCTYP == 'V':
                    self._VRECS['DCVVOLSR'].append(restrec[22:28].decode('cp500').strip())
                    self._VRECS['DCVPERCT'].append(int(restrec[33:34].hex(),16))

                    DCVCYLMG = int(bin(restrec[119]),2) & 0b10000000 == True
                    fresp = int(restrec[34:38].hex(),16)
                    alloc = int(restrec[38:42].hex(),16)
                    vlcap = int(restrec[42:46].hex(),16)
                    if DCVCYLMG:
                        fresp *= 1024
                        alloc *= 1024
                        vlcap *= 1024
                    self._VRECS['DCVFRESP'].append(fresp)
                    self._VRECS['DCVALLOC'].append(alloc)
                    self._VRECS['DCVVLCAP'].append(vlcap)

                    self._VRECS['DCVFRAGI'].append(int(restrec[46:50].hex(),16))
                    self._VRECS['DCVLGEXT'].append(int(restrec[50:54].hex(),16))
                    self._VRECS['DCVFREXT'].append(int(restrec[54:58].hex(),16))
                    self._VRECS['DCVFDSCB'].append(int(restrec[58:62].hex(),16))
                    self._VRECS['DCVFVIRS'].append(int(restrec[62:66].hex(),16))

                    self._VRECS['DCVDVTYP'].append(restrec[66:74].decode('cp500').strip())

                    # maybe want 'int' value?
                    self._VRECS['DCVDVNUM'].append(hex(int(restrec[74:76].hex(),16)))
                    
                    self._VRECS['DCVSGTCL'].append(restrec[80:110].decode('cp500').strip())
                    self._VRECS['DCVDPTYP'].append(restrec[110:118].decode('cp500').strip())

                    self.records_parsed['V'] += 1

            self.drecs = pd.DataFrame.from_dict(self._DRECS)
            del self._DRECS
            self.vrecs = pd.DataFrame.from_dict(self._VRECS)
            del self._VRECS
            self._state = self.STATE_READY

    def parse(self):
        """
        Function to parse the dcollect file as a background thread.
        This is a non-blocking function to parse the dcollect data.
        Status of background parsing can be queried via the .status attribute.

        Example usage::

            >>> from mfpandas import DCOLLECT
            >>> d = DCOLLECT(dcollect='/path/to/binary/dcollect/file') 
            >>> d.parse()       

        """        
        pt = threading.Thread(target=self.parse_t)
        pt.start()
        return True
    
    def parse_fancycli(self):
        """
        Function to parse the dcollect file as a background thread with some fancy graphics in the commandline.
        This is a non-blocking function to parse the dcollect data.

        Example usage::

            >>> d = DCOLLECT('/path/to/binary/dcollect/file')
            >>> d.parse_fancycli()
            24-06-30 15:07:07 - parsing /path/to/binary/dcollect/file
            24-06-30 15:07:07 - Still Parsing your input
            24-06-30 15:07:08 - Done.
            24-06-30 15:07:08   - 37 V-records seen, 37 parsed
            24-06-30 15:07:08   - 6704 D-records seen, 6704 parsed
            24-06-30 15:07:08   - 1392 A-records seen, 0 parsed
            24-06-30 15:07:08   - 12 DC-records seen, 0 parsed
            24-06-30 15:07:08   - 12 SC-records seen, 0 parsed
            24-06-30 15:07:08   - 2 MC-records seen, 0 parsed
            24-06-30 15:07:08   - 11 SG-records seen, 0 parsed
            24-06-30 15:07:08   - 471 VL-records seen, 0 parsed
            24-06-30 15:07:08   - 1 BC-records seen, 0 parsed
            24-06-30 15:07:08   - 1 AI-records seen, 0 parsed
            >>> 


        """            
        print(f'{datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")} - parsing {self._dcolfile}')
        self.parse()
        while self._state < self.STATE_READY:
            print(f'{datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")} - {self.status["status"]}', end='\r', flush=True)
            time.sleep(0.5)
        print('')
        print(f'{datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")} - Done.')
        for t in self.records_parsed:
            print(f'{datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S")}   - {self.records_seen[t]} {t}-records seen, {self.records_parsed[t]} parsed')

    def _save_pickle(self, df='', dfname='', path='', prefix=''):     
        # Sanity check
        if self._state != self.STATE_READY:
            raise UsageError('Not done parsing yet!')
        
        df.to_pickle(f'{path}/{prefix}{dfname}.pickle')

    def save_pickles(self, path=None, prefix=None):
        """Saves the generated DataFrames into pickles so you can quickly
        use them again in another run.

        :param path: Path to where the pickles will be saved
        :type path: path
        :param prefix: Prefix for the pickle files (optional)
        :type prefix: str
        :raises UsageError: If not done parsing yet
        :raises UsageError: If path does not exist and cannot be created
        :raises UsageError: If the pickle file cannot be created
        :return: True is success, UsageError is failure
        :rtype: bool

        """
        if self._state != self.STATE_READY:
            raise UsageError("Not done parsing yet!")
        if not os.path.exists(path):
            madedir = os.system(f'mkdir -p {path}')
            if madedir != 0:
                raise UsageError(f'{path} does not exist, and cannot be created') 
        for frame,name in [(self.drecs,'DRECS'), (self.vrecs,'VRECS')]:
            self._save_pickle(frame, dfname=name, path=path, prefix=prefix)
        return True

    
    @property
    def status(self):
        """
        Retrieves status of our background task.

        Example usage::

            >>> d = DCOLLECT('/path/to/binary/dcollect/file')
            >>> d.parse()
            >>> d.status
            {'status': 'Ready', 'records_seen': {'V': 37, 'D': 6704, 'A': 1392, 'DC': 12, 'SC': 12, 'MC': 2, 'SG': 11, 'VL': 471, 'BC': 1, 'AI': 1}, 'records_parsed': {'V': 37, 'D': 6704, 'A': 0, 'DC': 0, 'SC': 0, 'MC': 0, 'SG': 0, 'VL': 0, 'BC': 0, 'AI': 0}}
            >>> 


        """       
        if self._state == self.STATE_READY:
            return {'status': 'Ready', 'records_seen': self.records_seen, 'records_parsed': self.records_parsed}
        else:
            return {'status': "Still Parsing your input", 'records_seen': self.records_seen, 'records_parsed': self.records_parsed}
        
    @property
    def datasets(self):
        """
        Returns a Pandas Dataframe with all the parsed "D"-records. (datasets).


        For an explanation of the fields go to : https://www.ibm.com/docs/en/zos/3.1.0?topic=output-dcollect-record-structure
        """              
        if self._state != self.STATE_READY:
            print('no can do make nice error')
        else:
            return self.drecs
    
    @property
    def volumes(self):
        if self._state != self.STATE_READY:
            print('error also here')
        else:
            return self.vrecs
        

    def datsets_on_volume(self, volser=None):
        """
        Returns a sorted list of all datasets on a volume.

        
        :param volume: Volume Serial 
        :type volume: str
        :raise UsageError: If unknown volume.
        """        
        volser_check = self.vrecs.loc[self.vrecs.DCVVOLSR==volser]
        if len(volser_check) == 0:
            raise UsageError(f"Volser {volser} not found")
        datasets = list(self.drecs.loc[self.drecs.DCDVOLSR==volser]['DCDDSNAM'].values)
        datasets.sort()
        return datasets
    
    
   
            



