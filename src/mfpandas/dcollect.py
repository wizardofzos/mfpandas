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

        Recordtypes supported: D (Datasets), V (Volumes), DC (DataClass).

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

        self._DCRECS = {
            # Header Information
            'DDCNAME': [],       # Name of Data Class
            'DDCUSER': [],       # Userid of last updater
            'DDCDATE': [],       # Date of last update
            'DDCTIME': [],       # Time of last update
            'DDCDESC': [],       # Description
            
            # Specification Flags (DDCSPEC1)
            'DDCFRORG': [],      # RECORG specified
            'DDCFLREC': [],      # LRECL specified
            'DDCFRFM': [],       # RECFM specified
            'DDCFKLEN': [],      # KEYLEN specified
            'DDCFKOFF': [],      # KEYOFF specified
            'DDCFEXP': [],       # Expiration attribute specified
            'DDCFRET': [],       # Retention attribute specified
            'DDCFPSP': [],       # Primary space specified
            
            # Specification Flags (DDCSPEC2)
            'DDCFSSP': [],       # Secondary space specified
            'DDCFDIR': [],       # Directory blocks specified
            'DDCFAUN': [],       # Allocation unit specified
            'DDCFAVR': [],       # AVGREC specified
            'DDCFVOL': [],       # Volume count specified
            'DDCFCIS': [],       # Data CI size specified
            'DDCFCIF': [],       # Free CI % specified
            'DDCFCAF': [],       # Free CA % specified
            
            # Specification Flags (DDCSPEC3)
            'DDCFXREG': [],      # SHAREOPT XREGION specified
            'DDCFXSYS': [],      # SHAREOPT XSYSTEM specified
            'DDCFIMBD': [],      # VSAM IMBED specified
            'DDCFRPLC': [],      # VSAM REPLICATE specified
            'DDCFCOMP': [],      # Compaction specified
            'DDCFMEDI': [],      # Media type specified
            'DDCFRECT': [],      # Recording technology specified
            'DDCFVEA': [],       # VSAM extended addressing
            
            # Specification Flags (DDCSPEC4)
            'DDCSPRLF': [],      # Space constraint relief
            'DDCREDUS': [],      # Reduce space by % specified
            'DDCRABS': [],       # Rec access bias specified
            'DDCFCT': [],        # Compression type specified
            'DDCBLMT': [],       # Block size limit specified
            'DDCCFS': [],        # RLS CF cache specified
            'DDCDVCS': [],       # Dynamic volume count specified
            'DDCFSCAL': [],      # Performance scaling specified
            
            # Data Set Attributes
            'DDCRCORG': [],      # Data set RECORG
            'DDCRECFM': [],      # Data set RECFM
            'DDCBLK': [],        # Blocked (1) or Unblocked (0)
            'DDCSTSP': [],       # Standard or spanned
            'DDCCNTL': [],       # Carriage control
            'DDCRETPD': [],      # Retention period
            'DDCEXPYR': [],      # Expiration year
            'DDCEXPDY': [],      # Expiration day of year
            'DDCVOLCT': [],      # Max volume count
            'DDCDSNTY': [],      # DSN type
            
            # Space Attributes
            'DDCSPPRI': [],      # Primary space amount
            'DDCSPSEC': [],      # Secondary space amount
            'DDCDIBLK': [],      # Directory blocks
            'DDCAVREC': [],      # AVGREC (M, K, U)
            'DDCREDUC': [],      # Reduce primary/secondary by %
            'DDCRBIAS': [],      # VSAM record access bias
            'DDCDVC': [],        # Dynalloc vol count
            'DDCAUNIT': [],      # Allocation unit amount
            'DDCBSZLM': [],      # Block size limit
            'DDCLRECL': [],      # Record length
            
            # VSAM Attributes
            'DDCCISZ': [],       # CISIZE
            'DDCCIPCT': [],      # CI freespace %
            'DDCCAPCT': [],      # CA freespace %
            'DDCSHROP': [],      # VSAM share options
            'DDCXREG': [],       # XREGION share options
            'DDCXSYS': [],       # XSYSTEM share options
            'DDCIMBED': [],      # IMBED option
            'DDCREPLC': [],      # REPLICATE option
            'DDCKLEN': [],       # Key length
            'DDCKOFF': [],       # Key offset
            'DDCCAMT': [],       # Candidate amount
            
            # Mountable Device Attributes
            'DDCCOMP': [],       # Compaction type
            'DDCMEDIA': [],      # Media type
            'DDCRECTE': [],      # Recording technology
            
            # Record Sharing and Logging
            'DDCBWOTP': [],      # RWO type
            'DDCLOGRC': [],      # Sphere recoverability
            'DDCSPAND': [],      # Record spans CI ability
            'DDCFRLOG': [],      # CICSVR FRLOG type
            'DDCLOGLN': [],      # Log stream ID length
            'DDCLOGID': [],      # Log stream ID
            
            # Extended Specification Flags (DDCSPECX)
            'DDCBWOS': [],       # BWO specified
            'DDCLOGRS': [],      # Sphere recoverability specified
            'DDCSPANS': [],      # CI span specified
            'DDCLSIDS': [],      # Logstream ID specified
            'DDCFRLGS': [],      # CICSVR FRLOG specification
            'DDCFEXTC': [],      # Extent constraint specified
            'DDCFA2GB': [],      # RLS above 2GB specified
            'DDCFPSEG': [],      # Performance segmentation specified
            
            # Extended Specification Flags (DDCSPECB)
            'DDCFKYL1': [],      # Keylabel 1 specified
            'DDCFKYC1': [],      # Keycode 1 specified
            'DDCFKYL2': [],      # Keylabel 2 specified
            'DDCFKYC2': [],      # Keycode 2 specified
            'DDCFVSP': [],       # SMBVSP specified
            'DDCFSDB': [],       # SDB specified
            'DDCFOVRD': [],      # Override JCK specified
            'DDCFCAR': [],       # CA reclaim specified
            
            # Extended Specification Flags (DDCSPECC)
            'DDCFATTR': [],      # EATTR specified
            'DDCFLOGR': [],      # Log replication specified
            'DDCFRMOD': [],      # VSAM SMB RMODE31 specified
            'DDCGSRDU': [],      # Guaranteed space reduction
            'DDCFKLBL': [],      # DASD data set key label specified
            
            # VSAM Extended Attributes
            'DDCREUSE': [],      # Reuse on open
            'DDCSPEED': [],      # Speed mode
            'DDCEX255': [],      # Over 255 extents allowed
            'DDCLOGRP': [],      # Log replication
            'DDCEATTR': [],      # Extended attribute
            'DDCCT': [],         # Compression type
            'DDCDSCF': [],       # RLS CF cache value
            'DDCA2GB': [],       # RLS above 2GB bar
            'DDCRECLM': [],      # CA reclaim
            'DDCBSZL2': [],      # Block size limit value (lower 4 bytes)
            
            # Tape Attributes
            'DDCPSCA': [],       # Performance scaling
            'DDCPSEG': [],       # Performance segmentation
            
            # SMB VSP
            'DDCVSPUK': [],      # Unit is KB
            'DDCVSPUM': [],      # Unit is MB
            'DDCVSPV': [],       # SMBVSP value
            
            # Key Labels
            'DDCKLBL1': [],      # Keylabel 1 length
            'DDCKLBN1': [],      # Keylabel 1 name
            'DDCKYCD1': [],      # Keycode 1
            'DDCKLBL2': [],      # Keylabel 2 length
            'DDCKLBN2': [],      # Keylabel 2 name
            'DDCKYCD2': [],      # Keycode 2
            
            # DASD Data Set Key Label
            'DDCRMODE': [],      # VSAM SMB RMODE31 value
            'DDCDKLBN': []     # DASD key label name
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
                elif DCURCTYP == 'DC':
                    # --- Header Information ---
                    namelen = int(restrec[22:24].hex(), 16)
                    endp = 24 + namelen
                    self._DCRECS['DDCNAME'].append(restrec[24:endp].decode('cp500').strip())
                    self._DCRECS['DDCUSER'].append(restrec[54:62].decode('cp500').strip())
                    self._DCRECS['DDCDATE'].append(restrec[62:72].decode('cp500').strip())
                    self._DCRECS['DDCTIME'].append(restrec[74:82].decode('cp500').strip())
                    self._DCRECS['DDCDESC'].append(restrec[82:202].decode('cp500').strip())
                    
                    # --- Specification Flags (DDCSPEC1-DDCSPEC4) ---
                    ddcspec1 = restrec[202]  # Offset 204
                    ddcspec2 = restrec[203]  # Offset 205
                    ddcspec3 = restrec[204]  # Offset 206
                    ddcspec4 = restrec[205]  # Offset 207
                    
                    # DDCSPEC1 flags
                    self._DCRECS['DDCFRORG'].append(1 if (ddcspec1 & 0b10000000) else 0)
                    self._DCRECS['DDCFLREC'].append(1 if (ddcspec1 & 0b01000000) else 0)
                    self._DCRECS['DDCFRFM'].append(1 if (ddcspec1 & 0b00100000) else 0)
                    self._DCRECS['DDCFKLEN'].append(1 if (ddcspec1 & 0b00010000) else 0)
                    self._DCRECS['DDCFKOFF'].append(1 if (ddcspec1 & 0b00001000) else 0)
                    self._DCRECS['DDCFEXP'].append(1 if (ddcspec1 & 0b00000100) else 0)
                    self._DCRECS['DDCFRET'].append(1 if (ddcspec1 & 0b00000010) else 0)
                    self._DCRECS['DDCFPSP'].append(1 if (ddcspec1 & 0b00000001) else 0)
                    
                    # DDCSPEC2 flags
                    self._DCRECS['DDCFSSP'].append(1 if (ddcspec2 & 0b10000000) else 0)
                    self._DCRECS['DDCFDIR'].append(1 if (ddcspec2 & 0b01000000) else 0)
                    self._DCRECS['DDCFAUN'].append(1 if (ddcspec2 & 0b00100000) else 0)
                    self._DCRECS['DDCFAVR'].append(1 if (ddcspec2 & 0b00010000) else 0)
                    self._DCRECS['DDCFVOL'].append(1 if (ddcspec2 & 0b00001000) else 0)
                    self._DCRECS['DDCFCIS'].append(1 if (ddcspec2 & 0b00000100) else 0)
                    self._DCRECS['DDCFCIF'].append(1 if (ddcspec2 & 0b00000010) else 0)
                    self._DCRECS['DDCFCAF'].append(1 if (ddcspec2 & 0b00000001) else 0)
                    
                    # DDCSPEC3 flags
                    self._DCRECS['DDCFXREG'].append(1 if (ddcspec3 & 0b10000000) else 0)
                    self._DCRECS['DDCFXSYS'].append(1 if (ddcspec3 & 0b01000000) else 0)
                    self._DCRECS['DDCFIMBD'].append(1 if (ddcspec3 & 0b00100000) else 0)
                    self._DCRECS['DDCFRPLC'].append(1 if (ddcspec3 & 0b00010000) else 0)
                    self._DCRECS['DDCFCOMP'].append(1 if (ddcspec3 & 0b00001000) else 0)
                    self._DCRECS['DDCFMEDI'].append(1 if (ddcspec3 & 0b00000100) else 0)
                    self._DCRECS['DDCFRECT'].append(1 if (ddcspec3 & 0b00000010) else 0)
                    self._DCRECS['DDCFVEA'].append(1 if (ddcspec3 & 0b00000001) else 0)
                    
                    # DDCSPEC4 flags
                    self._DCRECS['DDCSPRLF'].append(1 if (ddcspec4 & 0b10000000) else 0)
                    self._DCRECS['DDCREDUS'].append(1 if (ddcspec4 & 0b01000000) else 0)
                    self._DCRECS['DDCRABS'].append(1 if (ddcspec4 & 0b00100000) else 0)
                    self._DCRECS['DDCFCT'].append(1 if (ddcspec4 & 0b00010000) else 0)
                    self._DCRECS['DDCBLMT'].append(1 if (ddcspec4 & 0b00001000) else 0)
                    self._DCRECS['DDCCFS'].append(1 if (ddcspec4 & 0b00000100) else 0)
                    self._DCRECS['DDCDVCS'].append(1 if (ddcspec4 & 0b00000010) else 0)
                    self._DCRECS['DDCFSCAL'].append(1 if (ddcspec4 & 0b00000001) else 0)
                    
                    # --- Data Set Attributes ---
                    ddcrcorg = int(restrec[206:207].hex(), 16)
                    rcorgmap = {
                        0: 'NULL_-SAM',
                        1: 'VSAM_KSDS',
                        2: 'VSAM_ESDS',
                        3: 'VSAM_RRDS',
                        4: 'VSAM_LDS'
                    }
                    self._DCRECS['DDCRCORG'].append(rcorgmap[ddcrcorg])
                    ddcrecfm = int(restrec[207:208].hex(), 16)
                    recfmmap = {
                        0: 'NULL',
                        1: 'UNDEFINED',
                        2: 'VARIABLE',
                        3: 'VARIABLE_SPANNED',
                        4: 'VARIABLE_BLOCKED',
                        5: 'VARIABLE_BLOCKED_SPANNED',
                        6: 'FIXED',
                        7: 'FIXED_STANDARD',
                        8: 'FIXED_BLOCKED',
                        9: 'FIXED_BLOCKED_SPANNED'}
                    self._DCRECS['DDCRECFM'].append(recfmmap[ddcrecfm])
                    
                    ddcdsflg = restrec[208]  # Offset 210
                    self._DCRECS['DDCBLK'].append(1 if (ddcdsflg & 0b10000000) else 0)
                    self._DCRECS['DDCSTSP'].append(1 if (ddcdsflg & 0b01000000) else 0)
                    
                    self._DCRECS['DDCCNTL'].append(int(restrec[209:210].hex(), 16))
                    
                    # Date/Time fields (Alternative interpretations based on which flag is set)
                    self._DCRECS['DDCRETPD'].append(int(restrec[210:214].hex(), 16))  # Signed 4
                    self._DCRECS['DDCEXPYR'].append(int(restrec[210:212].hex(), 16))  # Signed 2
                    self._DCRECS['DDCEXPDY'].append(int(restrec[212:214].hex(), 16))  # Signed 2
                    self._DCRECS['DDCVOLCT'].append(int(restrec[214:216].hex(), 16))
                    self._DCRECS['DDCDSNTY'].append(int(restrec[216:218].hex(), 16))
                    
                    # --- Space Attributes ---
                    self._DCRECS['DDCSPPRI'].append(int(restrec[218:222].hex(), 16))
                    self._DCRECS['DDCSPSEC'].append(int(restrec[222:226].hex(), 16))
                    self._DCRECS['DDCDIBLK'].append(int(restrec[226:230].hex(), 16))
                    avrecmap = {
                        0: "NONE",
                        1: "BYTES",
                        2: "KILOBYTES",
                        3: "MEGABYTES"
                    }
                    self._DCRECS['DDCAVREC'].append(avrecmap[int(restrec[230:231].hex(), 16)])
                    self._DCRECS['DDCREDUC'].append(int(restrec[231:232].hex(), 16))
                    biasmap = {
                        0: "USER",
                        1: "SYSTEM"
                    }
                    self._DCRECS['DDCRBIAS'].append(biasmap[int(restrec[232:233].hex(), 16)])
                    self._DCRECS['DDCDVC'].append(int(restrec[233:234].hex(), 16))
                    self._DCRECS['DDCAUNIT'].append(int(restrec[234:238].hex(), 16))
                    self._DCRECS['DDCBSZLM'].append(int(restrec[238:242].hex(), 16))
                    self._DCRECS['DDCLRECL'].append(int(restrec[242:246].hex(), 16))
                    
                    # --- VSAM Attributes ---
                    self._DCRECS['DDCCISZ'].append(int(restrec[246:250].hex(), 16))
                    self._DCRECS['DDCCIPCT'].append(int(restrec[250:252].hex(), 16))  # Signed
                    self._DCRECS['DDCCAPCT'].append(int(restrec[252:254].hex(), 16))  # Signed
                    self._DCRECS['DDCSHROP'].append(int(restrec[254:256].hex(), 16))  # Signed
                    self._DCRECS['DDCXREG'].append(int(restrec[254:255].hex(), 16))
                    self._DCRECS['DDCXSYS'].append(int(restrec[255:256].hex(), 16))
                    
                    ddcvindx = restrec[256]  # Offset 258
                    self._DCRECS['DDCIMBED'].append(1 if (ddcvindx & 0b10000000) else 0)
                    self._DCRECS['DDCREPLC'].append(1 if (ddcvindx & 0b01000000) else 0)
                    
                    self._DCRECS['DDCKLEN'].append(int(restrec[257:258].hex(), 16))
                    self._DCRECS['DDCKOFF'].append(int(restrec[258:260].hex(), 16))
                    self._DCRECS['DDCCAMT'].append(int(restrec[260:261].hex(), 16))
                    
                    # --- Mountable Device Attributes ---
                    compmap = {
                        0: "DDCCNUL",
                        1: "DDCNOCMP",
                        2: "DDCIDRC"
                    }
                    self._DCRECS['DDCCOMP'].append(compmap[int(restrec[262:263].hex(), 16)])
                    mediamap = {
                        0: "NULL",
                        1: "CARTRIDGE_SYSTEM",
                        2: "ENHANCHED_CAPACITY_CARTTIDGE_SYSTEM",
                        3: "HIGH_PERMFORMANCE",
                        4: "RESERVED_EXTENDED_HIGH"
                    }
                    self._DCRECS['DDCMEDIA'].append(mediamap[int(restrec[263:264].hex(), 16)])
                    rectemap = {
                        0: "NULL",
                        1: "18-TRACK",
                        2: "36-TRACK"
                    }
                    self._DCRECS['DDCRECTE'].append(rectemap[int(restrec[264:265].hex(), 16)])
                    # Offset 265 reserved
                    
                    # --- Record Sharing & Logging (DDCRLS1) ---
                    bwotpmap = {
                        0: "0",
                        1: "CICS",
                        2: "NONE",
                        3: "IMS"
                    }
                    self._DCRECS['DDCBWOTP'].append(bwotpmap[int(restrec[266:267].hex(), 16)])
                    logrcmap = {
                        0: "0",
                        1: "NON-RECOVERABLE_SPHERE",
                        2: "UNDO_USE_EXERNAL_LOG",
                        3: "ALL_UNDO_AND_FORWARD"
                    }
                    self._DCRECS['DDCLOGRC'].append(logrcmap[int(restrec[267:268].hex(), 16)])
                    spandmap = {
                        0: "RECORD_CANNOT_SPAN_CI",
                        1: "RECORD_MAY_SPAN_CI"
                    }
                    self._DCRECS['DDCSPAND'].append(spandmap[int(restrec[268:269].hex(), 16)])
                    frlogmap = {
                        0: "0",
                        1: "NONE",
                        2: "REDO",
                        3: "UNDO",
                        6: "ALL"
                    }
                    self._DCRECS['DDCFRLOG'].append(frlogmap[int(restrec[269:270].hex(), 16)])
                    
                    # Log Stream ID (variable length)
                    self._DCRECS['DDCLOGLN'].append(int(restrec[270:272].hex(), 16))
                    self._DCRECS['DDCLOGID'].append(restrec[272:298].decode('cp500').strip())
                    
                    # --- Extended Specification Flags (DDCSPECX) ---
                    ddcspecx = restrec[298]   # Offset 300
                    ddcspecb = restrec[299]   # Offset 301
                    ddcspecc = restrec[300]   # Offset 302
                    
                    self._DCRECS['DDCBWOS'].append(1 if (ddcspecx & 0b10000000) else 0)
                    self._DCRECS['DDCLOGRS'].append(1 if (ddcspecx & 0b01000000) else 0)
                    self._DCRECS['DDCSPANS'].append(1 if (ddcspecx & 0b00100000) else 0)
                    self._DCRECS['DDCLSIDS'].append(1 if (ddcspecx & 0b00010000) else 0)
                    self._DCRECS['DDCFRLGS'].append(1 if (ddcspecx & 0b00001000) else 0)
                    self._DCRECS['DDCFEXTC'].append(1 if (ddcspecx & 0b00000100) else 0)
                    self._DCRECS['DDCFA2GB'].append(1 if (ddcspecx & 0b00000010) else 0)
                    self._DCRECS['DDCFPSEG'].append(1 if (ddcspecx & 0b00000001) else 0)
                    
                    # DDCSPECB flags
                    self._DCRECS['DDCFKYL1'].append(1 if (ddcspecb & 0b10000000) else 0)
                    self._DCRECS['DDCFKYC1'].append(1 if (ddcspecb & 0b01000000) else 0)
                    self._DCRECS['DDCFKYL2'].append(1 if (ddcspecb & 0b00100000) else 0)
                    self._DCRECS['DDCFKYC2'].append(1 if (ddcspecb & 0b00010000) else 0)
                    self._DCRECS['DDCFVSP'].append(1 if (ddcspecb & 0b00001000) else 0)
                    self._DCRECS['DDCFSDB'].append(1 if (ddcspecb & 0b00000100) else 0)
                    self._DCRECS['DDCFOVRD'].append(1 if (ddcspecb & 0b00000010) else 0)
                    self._DCRECS['DDCFCAR'].append(1 if (ddcspecb & 0b00000001) else 0)
                    
                    # DDCSPECC flags
                    self._DCRECS['DDCFATTR'].append(1 if (ddcspecc & 0b10000000) else 0)
                    self._DCRECS['DDCFLOGR'].append(1 if (ddcspecc & 0b01000000) else 0)
                    self._DCRECS['DDCFRMOD'].append(1 if (ddcspecc & 0b00100000) else 0)
                    self._DCRECS['DDCGSRDU'].append(1 if (ddcspecc & 0b00010000) else 0)
                    self._DCRECS['DDCFKLBL'].append(1 if (ddcspecc & 0b00001000) else 0)
                    
                    # --- More VSAM/Extended Attributes ---
                    ddcvsam1 = restrec[303]   # Offset 305 (DDCVBYT1)
                    self._DCRECS['DDCREUSE'].append(1 if (ddcvsam1 & 0b10000000) else 0)
                    self._DCRECS['DDCSPEED'].append(1 if (ddcvsam1 & 0b01000000) else 0)
                    self._DCRECS['DDCEX255'].append(1 if (ddcvsam1 & 0b00100000) else 0)
                    self._DCRECS['DDCLOGRP'].append(1 if (ddcvsam1 & 0b00010000) else 0)
                    
                    # Offsets 306-308 reserved (3 bytes)
                    self._DCRECS['DDCEATTR'].append(int(restrec[307:308].hex(), 16))
                    ctmap = {
                        0: "GENERIC",
                        1: "TAILORED",
                        2: "ZR",
                        3: "ZR"
                    }
                    self._DCRECS['DDCCT'].append(ctmap[int(restrec[308:309].hex(), 16)])
                    dscfmap = {
                        0: "ALL",
                        1: "UPDATEDONLY",
                        2: "NONE"
                    }
                    self._DCRECS['DDCDSCF'].append(dscfmap[int(restrec[309:310].hex(), 16)])
                    
                    ddcrbyte = restrec[310]   # Offset 312
                    self._DCRECS['DDCA2GB'].append(1 if (ddcrbyte & 0b01000000) else 0)
                    self._DCRECS['DDCRECLM'].append(1 if (ddcrbyte & 0b00100000) else 0)
                    
                    # DDCBLKLM / DDCBSZLM at offset 317 -> index 315
                    self._DCRECS['DDCBSZL2'].append(int(restrec[315:319].hex(), 16))
                    
                    # --- Tape Attributes ---
                    self._DCRECS['DDCPSCA'].append(int(restrec[319:320].hex(), 16))
                    self._DCRECS['DDCPSEG'].append(int(restrec[320:321].hex(), 16))
                    # Offsets 323-325 reserved (5 bytes total)
                    
                    # SMB VSP field
                    ddcvsp = restrec[326]     # Offset 328
                    self._DCRECS['DDCVSPUK'].append(1 if (ddcvsp & 0b10000000) else 0)
                    self._DCRECS['DDCVSPUM'].append(1 if (ddcvsp & 0b01000000) else 0)
                    self._DCRECS['DDCVSPV'].append(int(restrec[327:330].hex(), 16))
                    
                    # --- Key Labels ---
                    self._DCRECS['DDCKLBL1'].append(int(restrec[330:332].hex(), 16))
                    self._DCRECS['DDCKLBN1'].append(restrec[332:396].decode('cp500').strip())
                    self._DCRECS['DDCKYCD1'].append(int(restrec[396:397].hex(), 16))
                    # Offset 397 filler
                    
                    self._DCRECS['DDCKLBL2'].append(int(restrec[398:400].hex(), 16))
                    self._DCRECS['DDCKLBN2'].append(restrec[400:464].decode('cp500').strip())
                    self._DCRECS['DDCKYCD2'].append(int(restrec[464:465].hex(), 16))
                    # Offset 465 filler, 466 reserved
                    rmodemap = {
                        0: "BLANK",
                        1: "ALL",
                        2: "BUFF",
                        3: "CB",
                        4: "NONE"
                    }
                    self._DCRECS['DDCRMODE'].append(rmodemap[int(restrec[467:468].hex(), 16)])
                    
                    # DASD Data Set Key Label
                    labellen = int(restrec[468:470].hex(), 16)
                    endlab = 470 + labellen
                    self._DCRECS['DDCDKLBN'].append(restrec[470:endlab].decode('cp500').strip())
                    
                    # Offsets 536-563 reserved (28 bytes)
                    
                    self.records_parsed['DC'] += 1

            self.drecs = pd.DataFrame.from_dict(self._DRECS)
            del self._DRECS
            self.vrecs = pd.DataFrame.from_dict(self._VRECS)
            del self._VRECS
            self.dcrecs = pd.DataFrame.from_dict(self._DCRECS)
            del self._DCRECS
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
        
    @property
    def dataclasses(self):
        if self._state != self.STATE_READY:
            print('Not done parsing yet')
        else:
            return self.dcrecs

    def datasets_on_volume(self, volser=None):
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
    
    
   
            



