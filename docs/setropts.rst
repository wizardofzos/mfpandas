Working with SETROPTS LIST data
###############################

The :py:class:`mfpandas.SETROPTS` is made to work with your SETROPTS data. 
Because parsing the output of `SETROPTS LIST` is troublesome to say the least a REXX
is provided to create the SETROPTS export this class can work with.


This REXX is retrieved from the SETROPTS class like below::

    >>> s = SETROPTS()
    >>> print(s.extractREXX)
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



SETROPTS Examples
*****************

RACF Class Check
-----------------

Suppose we need to create a list of all classes that are not RACLISTed not GLOBAL but are ACTIVE and GENERIC:: 

    >>> from mfpandas import SETROPTS
    >>> s = SETROPTS(setropts='/home/henri/WIZARD.SETROPTS.D250101')
    >>> a = s.classInfo.loc[(s.classInfo.RACLIST=="NO") & 
                            (s.classInfo.GENERIC=='YES') &
                            (s.classInfo.CLASSACT=='YES') &
                            (s.classInfo.GLOBAL=='NO')
                           ]['name'].values
    >>> print(','.join(a))
    PKISERV,CACHECLS,RACFEVNT,FSACCESS,IIMS,PRINTSRV,MDSNJR,LIMS,MDSNSC,LDAPBIND,VMDEV,RACFVARS,MDSNSP,RIMS,LDAP,JAVA,CRYPTOZ,MDSNSQ,MDSNUF,ILMADMIN,MDSNUT,VMLAN,MDSNGV,SYSAUTO,RAUDITX


