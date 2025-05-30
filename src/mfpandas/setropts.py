import os
from datetime import datetime
import pandas as pd 
import glob 

# No mess with my header lines in XLSX
import pandas.io.formats.excel
pandas.io.formats.excel.ExcelFormatter.header_style = None

class SETROPTSUsageError(Exception):
    """Raised when a usage error occurs."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class SETROPTS:

    """
    :param setropts: Full path to SETROPTS extract file
    :type setropts: str
    :param pickles: Full patch to folder with pre-saved pickle files (optional)
    :type pickles: str
    :param prefix: Prefix for pickle files (optional)
    :type prefix: str

    This class contains code to parse the output of an IRRXUTIL _SETROPTS extract dataset.

    After parsing you get a two pandas DataFrames. One with all the 'key-value' pairs and 
    one with the class information (which classes are RACLISTed, GENERIC etc.) 

    To create the IRRXUTIL _SETROPTS extract dataset run the REXX as provided by the `extractRexx` method::

        /* REXX */ 
                                                                
        /* Our output stem */ 
        out. = '' 
        out.0 = 0 
                                                                
        /* Our output dataset */ 
        d = date('S') 
        d = substr(d,3,6) 
        outdsn = userid()".SETROPTS.D"d 
                                                                
                                                                
        myrc=IRRXUTIL("EXTRACT","_SETROPTS","_SETROPTS","RES") 
        if (word(myrc,1)<>0) then do 
            say "MYRC="myrc 
            say "An IRRXUTIL or R_admin error occurred " 
            exit 1 
        end 
                                                            
        do s = 1 to RES.BASE.0 
            setr = RES.BASE.s 
            if RES.BASE.setr.0 = 1 then do 
                no = out.0 + 1 
                out.no = setr":"RES.BASE.setr.1 
                out.0 = no 
            end 
            else do 
                if RES.BASE.setr.0 = 0 then iterate 
                do t = 1 to RES.BASE.setr.0 
                    stem = RES.BASE.setr.t 
                    no = out.0 + 1 
                    out.no = setr":"stem 
                    out.0 = no 
                end 
            end 
        end 
        say "Writing " out.0 "SETROPTS key/value pairs to" outdsn 
                                                                    
        /* Time to write that stuff */ 
        "ALLOC DA('"outdsn"') SPACE(1,10) CYL    " || , 
        "LRECL(80) RECFM(F B) BLKSIZE(8000) FI(OUTDD) NEW" 
                                                                    
        "EXECIO * DISKW OUTDD (STEM out. FINIS" 
                                                                    
        say "Done"     

            
    Then, transfer "<USERID>.SETROPTS.D<YYMMDD>" to your machine. Make sure this is an ASCII transfer.
   
    Documentation used to help create this...

    * https://www.ibm.com/docs/en/zos/3.1.0?topic=tables-setropts-administration
    * https://www.ibm.com/docs/en/zos/2.4.0?topic=extract-setropts-data
    * https://www.ibm.com/docs/en/zos/2.5.0?topic=setup-erasing-scratched-released-data-erase-option 
    * https://share.confex.com/share/124/webprogram/Handout/Session16807/RSH%20Consulting%20-%20RACF%20SETROPTS%20-%202015-03%20-%20SHARE%20-%2016807.pdf 


    """


    
    _setropts_fields = {
    "ADDCREAT": "ADCREATOR IN EFFECT (TRUE/FALSE)", 
    "ADSP": "AUTOMATIC DATASET PROTECTION IS EFFECT (TRUE/FALSE)", 
    "APPLAUDT": "APPLAUDIT IN EFFECT (TRUE/FALSE)",
    "CATDSNS": "CATALOGUED DATA SETS ONLY IN EFFECT (TRUE/FALSE)",
    "CMDVIOL": "ATTRIBUTE SETTING: RACF command violations are logged",
    "COMPMODE": "COMPATIBILITY MODE IN EFFECT (TRUE/FALSE)",
    "EGN": "ENHANCED GENERIC NAMING IS IN EFFECT (TRUE/FALSE()",
    "ERASE": "ERASE-ON-SCRATCH IS ACTIVE (TRUE/FALSE)",
    "ERASEALL": "ERASE-ON-SCRATCH FOR ALL (TRUE/FALSE)",
    "ERASESEC": "ERASE-ON-SCRATCH FOR SECLEVEL (SECLEVEL VALUE/FALSE)",
    "GENOWNER": "GENERIC OWNER ONLY IN EFFECT (TRUE/FALSE)",
    "GRPLIST": "LIST OF GROUPS ACCESS CHECKING IS ACTIVE (TRUE/FALSE)",
    "HISTORY": "GENERATIONS OF PREVIOUS PASSWORDS BEING MAINTAINED (AMOUNT)",
    "INACTIVE": "INACTIVE USERIDS ARE BEING AUTOMATICALLY REVOKED AFTER xx DAYS (AMOUNT/FALSE)",
    "INITSTAT": "ATTRIBUTE SETTING: records statistics on all user profiles in the system",
    "INTERVAL": "PASSWORD INTERVAL",
    "JESBATCH": "JES-BATCHALLRACF OPTION IS ACTIVE (TRUE/FALSE)",
    "JESEARLY": "JES-EARLYVERIFY OPTION IS ACTIVE (TRUE/FALSE)",
    "JESNJE": "USER-ID FOR JES NJEUSERID (USERID/UNDEFINED)",
    "JESUNDEF": "USER-ID FOR JES UNDEFINEDUSER (USERID/UNDEFINED)",
    "JESXBM": "JES-XBMALLRACF OPTION IS ACTIVE (TRUE/FALSE)",
    "KERBLVL": "KERBLVL (OBSOLETE SINCE 1.9)",
    "MINCHANG": "PASSWORD MINIMUM CHANGE INTERVAL (AMOUNT)", 
    "MIXDCASE": "MIXED CASE PASSWORD SUPPORT IS IN EFFECT (TRUE/FALSE)",
    "MLACTIVE": "MULTI-LEVEL ACTIVE IS IN EFFECT (TRUE/FALSE) ",
    "MLFS": "MULTI-LEVEL FILE SYSTEM IS  IN EFFECT (TRUE/FALSE)",
    "MLIPC": "MULTI-LEVEL INTERPROCESS COMMUNICATIONS IS IN EFFECT (TRUE/FALSE)",
    "MLNAMES": "MULTI-LEVEL NAME HIDING IS IN EFFECT (TRUE/FALSE)",
    "MLQUIET": "MULTI-LEVEL QUIET IS IN EFFECT TRUE/FALSE)",
    "MLS": "MLS IS IN EFFECT (TRUE/FALSE)",
    "MLSTABLE": "MULTI-LEVEL STABLE IS IN EFFECT (TRUE/FALSE)",
    "MODEL": "DATA SET MODELLING BEING DONE (TRUE/FALSE)",
    "MODGDG": "MODGDG IS ACTIVE (TRUE/FALSE)",
    "MODGROUP": "MODGROUP IS ACTIVE (TRUE/FALSE)",
    "MODUSER": "MODUSER IS ACTIVE (TRUE/FALSE)",
    "OPERAUDT": "ATTRIBUTE SETTING: RACF commands issued & resources accessed using OPERATIONS authority are logged",
    "PHRINT": "PASSPHRASE INTERVAL",
    "PREFIX": "SINGLE LEVEL NAME PREFIX",
    "PRIMLANG": "PRIMARY LANGUAGE DEFAULT",
    "PROTALL": "PROTECTALL (FAILURES/WARNING/OFF)",
    "PWDALG": "THE ACTIVE PASSWORD ENCRYPTION ALGORITHM", 
    "PWDSPEC": "SPECIAL CHARACTERS IN PASWORD ARE ALLOWED (TRUE/FALSE)", 
    "REALDSN": "REAL DATA SET NAMES OPTION IS ACTIVE (TRUE/FALSE)",
    "RETPD": "SECURITY RETENTION PERIOD (DAYS/FALSE)",
    "REVOKE": "CONSECUTIVE UNSUCCESSFUL PASSWORD ATTEMPTS REVOKING USER (AMOUNT/FALSE)",
    "RULES": "RACF PASSWORDRULES ACTIVE (TRUE/FALSE)",
    "RULE1": "PASSWORDRULE 1",
    "RULE2": "PASSWORDRULE 2",
    "RULE3": "PASSWORDRULE 3",
    "RULE4": "PASSWORDRULE 4",
    "RULE5": "PASSWORDRULE 5",
    "RULE6": "PASSWORDRULE 6",
    "RULE7": "PASSWORDRULE 7",
    "RULE8": "PASSWORDRULE 8",
    "SAUDIT": "ATTRIBUTE SETTING: RACF commands issued using SPECIAL authority are logged",
    "RVARSWPW": "RVARY SWITCH PASSWORD (DEFAULT/INSTLN)",
    "RVARSWFM": "THE ACTIVE RVARY SWITCH PASSWORD ENCRYPTION ALGORITHM",
    "RVARSTPW": "RVARY STATUS PASSWORD (DEFAULT/INSTLN)",
    "RVARSTFM": "THE ACTIVE RVARY STATUS PASSWORD ENCRYPTION ALGORITHM",
    "SECLABCT": "SECLABEL CONTROL IS IN EFFECT (TRUE/FALSE)",
    "SESSINT": "PARTNER LU-VERIFICATION SESSIONKEY INTERVAL MAXIMUM/DEFAULT (MINUTES/NOLIMIT)",
    "SLABAUDT": "SECLABEL AUDIT IS IN EFFECT (TRUE/FALSE)",
    "SLBYSYS": "SECURITY LABEL BY SYSTEM IS IN EFFECT (TRUE/FALSE)",
    "WARNING": "PASSWORD EXPIRATION WARNING LEVEL (DAYS/FALSE)",
    "TAPEDSN": "TAPE DATA SET PROTECTION IS ACTIVE (TRUE/FALSE)",
    "WHENPROG":  "ATTRIBUTE SETTING: Activates PROGRAM Class. Enables protection of program modules & use of conditional access to datasets via a specific program",
    "SECLANG":  "SECONDARY LANGUAGE DEFAULT",
    "TERMINAL": "ATTRIBUTE SETTING: Specifies the universal access (UACC) for undefined terminals"
    }
    _setropts_lists = [
        "CLASSACT",
        "CLASSTAT",
        "GENCMD",
        "GENERIC",
        "GENLIST",
        "GLOBAL",
        "RACLIST",
        "AUDIT",
        "LOGALWYS",
        "LOGNEVER",
        "LOGSUCC",
        "LOGFAIL",
        "LOGDEFLT"
    ]

    def __init__(self, setropts=None, pickles=None, prefix=None):
        if pickles == None:
            if setropts == None:
                pass
            else:
                self._setropts = setropts
                self._parse()
        else:
            # Read from pickles dir
            picklefiles = glob.glob(f'{pickles}/{prefix}*.pickle')
            for pickle in picklefiles:
                fname = os.path.basename(pickle)
                df = fname.replace(prefix,'').split('.')[0]
                if df == 'CINFO':
                    self._cinfo = pd.read_pickle(pickle)
                if df == 'FINFO':
                    self._finfo = pd.read_pickle(pickle)

        
    def _parse(self):
        with open(self._setropts, 'r') as f:
            kvpairs = f.read().splitlines()
        dict = {}
        
        for kv in kvpairs:
            parts = kv.split(':', maxsplit=1)
            key = parts[0].strip()
            value = parts[1].strip()
            if key in dict:
                dict[key].append(value)
            else:
                dict[key] = [value]
        options = {'Setting': [], 'Value': [], 'Meaning': []}
        lists = {}
        
 
            
        for f in self._setropts_lists:
            lists[f] = []
            
        for key in dict:
            if len(dict[key]) == 1:
                options['Setting'].append(key)
                try:
                    # EPLS convert to int if possible
                    dict[key][0] = int(dict[key][0])
                except:
                    dict[key][0] = dict[key][0]
                options['Value'].append(dict[key][0])
                options['Meaning'].append(self._setropts_fields[key])
            else:
                lists[key] = dict[key]
        # Fill not-specified ones
        for f in self._setropts_fields.keys():
            if f not in options['Setting']:
                options['Setting'].append(f)
                options['Meaning'].append(self._setropts_fields[f])
                if f == 'RULES':
                    options['Value'].append('TRUE')
                elif f == 'HISTORY':
                    options['Value'].append('0')
                elif f == 'SESSINT':
                    options['Value'].append('NOLIMIT')
                elif f == 'JESNJE' or  f == 'JESUNDEF':
                    options['Value'].append('UNDEFINED')
                elif f == 'PROTALL':
                    options['Value'].append('OFF')
                else:
                    options['Value'].append('FALSE')
                
        # Get our full list of all classes
        fulllist = []
        for l in lists:
            for i in lists[l]:
                fulllist.append(i)
        fulllist = list(set(fulllist)) 
        # build classinfo dict
        classinfo = {}
        classinfo['name'] = []
        for l in lists:
            classinfo[l] = []
        for c in fulllist:
            classinfo['name'].append(c)
            for t in lists:
                if c in lists[t]:
                    classinfo[t].append('YES')
                else:
                    classinfo[t].append('NO')
        self._cinfo = pd.DataFrame.from_dict(classinfo)
        self._finfo = pd.DataFrame.from_dict(options)  

    @property
    def classInfo(self):
        """Returns a dataframe with all class information fro SETROPTS as shown below::

        >>> s.classInfo
                 name CLASSACT CLASSTAT GENCMD GENERIC GENLIST GLOBAL RACLIST AUDIT LOGALWYS LOGNEVER LOGSUCC LOGFAIL LOGDEFLT
        0    ECICSDCT      YES       NO     NO      NO      NO     NO      NO    NO       NO       NO      NO      NO       NO
        1     IDTDATA      YES       NO     NO      NO      NO     NO      NO    NO       NO       NO      NO      NO       NO
        2         IZP      YES       NO     NO      NO      NO     NO      NO    NO       NO       NO      NO      NO       NO
        3    FSACCESS      YES       NO    YES     YES      NO     NO      NO    NO       NO       NO      NO      NO       NO
        4      GDSNSP      YES       NO     NO      NO      NO     NO      NO    NO       NO       NO      NO      NO       NO

        """        
        return self._cinfo 
    
    @property
    def fieldInfo(self):
        """Returns a dataframe with all the other information from SETROPTS. The `Meaning` column will give some extra information regarding the field.
        You can see below.::

            >>> s.fieldInfo
                Setting  Value                                            Meaning
            0   INITSTAT   TRUE  ATTRIBUTE SETTING: records statistics on all u...
            1   TERMINAL   READ  ATTRIBUTE SETTING: Specifies the universal acc...
            2   INTERVAL    180                                  PASSWORD INTERVAL
            3   MINCHANG      0          PASSWORD MINIMUM CHANGE INTERVAL (AMOUNT)
            4   MIXDCASE  FALSE  MIXED CASE PASSWORD SUPPORT IS IN EFFECT (TRUE...    

        
 
        """
        return self._finfo 
    
    def xlsx(self, filename=None):
        """This will create an XLSX file at the specified location with all the information parsed from the SETROPTS extract file."""
        writer = pd.ExcelWriter(filename, engine='xlsxwriter')   
        sheet = 'Classes'
        for df in [self._cinfo,self._finfo]:
            df.to_excel(writer, sheet_name=sheet, index=False)
            # Layout the XLSX
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                col_idx = df.columns.get_loc(column)
                writer.sheets[sheet].set_column(col_idx, col_idx, column_width+10)
            # Autofilter
            (max_row, max_col) = df.shape
            writer.sheets[sheet].autofilter(0, 0, max_row, max_col - 1)
            # Freeze first row
            writer.sheets[sheet].freeze_panes(1, 1)    
            sheet = 'Options'
        writer.close()
        
    @property 
    def extractREXX(self):
        rexx = """/* REXX */ 
                                                          
/* Our output stem */ 
out. = '' 
out.0 = 0 
                                                        
/* Our output dataset */ 
d = date('S') 
d = substr(d,3,6) 
outdsn = userid()".SETROPTS.D"d 
                                                        
                                                        
myrc=IRRXUTIL("EXTRACT","_SETROPTS","_SETROPTS","RES") 
if (word(myrc,1)<>0) then do 
    say "MYRC="myrc 
    say "An IRRXUTIL or R_admin error occurred " 
    exit 1 
end 
                                                    
do s = 1 to RES.BASE.0 
    setr = RES.BASE.s 
    if RES.BASE.setr.0 = 1 then do 
        no = out.0 + 1 
        out.no = setr":"RES.BASE.setr.1 
        out.0 = no 
    end 
    else do 
        if RES.BASE.setr.0 = 0 then iterate 
        do t = 1 to RES.BASE.setr.0 
            stem = RES.BASE.setr.t 
            no = out.0 + 1 
            out.no = setr":"stem 
            out.0 = no 
        end 
    end 
end 
say "Writing " out.0 "SETROPTS key/value pairs to" outdsn 
                                                            
/* Time to write that stuff */ 
"ALLOC DA('"outdsn"') SPACE(1,10) CYL    " || , 
"LRECL(80) RECFM(F B) BLKSIZE(8000) FI(OUTDD) NEW" 
                                                            
"EXECIO * DISKW OUTDD (STEM out. FINIS" 
                                                            
say "Done" 

"""
        return rexx
    
    def save_pickles(self, path='/tmp', prefix=''):
        """
        Saves the generated DataFrames into pickles so you can quickly
        use them again in another run.

        :param path: Full path to folder of the pickle files (default=/tmp)
        :type path: str
        :param prefix: Prefix for pickle files (optional)
        :type prefix: str

        """   
        # Is Path there ?
        if not os.path.exists(path):
            madedir = os.system(f'mkdir -p {path}')
            if madedir != 0:
                raise SETROPTSUsageError(f'{path} does not exist, and cannot create')
        # Let's save the pickles
        for df, dfname in [(self._cinfo,'CINFO'),(self._finfo,'FINFO')]:
            df.to_pickle(f'{path}/{prefix}{dfname}.pickle')