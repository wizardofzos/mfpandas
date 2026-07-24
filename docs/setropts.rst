Working with SETROPTS LIST data
###############################

The :py:class:`mfpandas.SETROPTS` is made to work with your SETROPTS data.
There are two ways to feed it:

* **Option A (recommended): the IRRXUTIL REXX.** Run the provided REXX on the
  mainframe to create a clean ``KEY:VALUE`` extract dataset and transfer it down.
* **Option B: convert existing ``SETROPTS LIST`` output.** If you already have a
  ``SETROPTS LIST`` capture (from a TSO session or the JES spool), convert it
  locally instead of running anything on the mainframe. See
  :ref:`setropts-list-conversion` below.


Option A: the IRRXUTIL REXX
***************************

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



.. _setropts-list-conversion:

Option B: convert SETROPTS LIST output
**************************************

If running the REXX is not convenient, you can convert a plain ``SETROPTS LIST``
capture into the same ``KEY:VALUE`` format. Both a TSO terminal capture and a
JES/SDSF spool capture (with ASA carriage-control) are handled.

Build a :py:class:`mfpandas.SETROPTS` directly from the captured text or a file::

    >>> from mfpandas import SETROPTS
    >>> s = SETROPTS.from_setropts_list('/home/henri/setropts-list.txt')
    >>> s.classInfo

Or convert to a ``KEY:VALUE`` file from the command line, then load it the same
way as a REXX extract::

    $ mfpandas-setropts-list setropts-list.txt -o WIZARD.SETROPTS.D250101
    >>> s = SETROPTS('WIZARD.SETROPTS.D250101')

.. note::

   The converter only emits the settings represented by the IRRXUTIL extract, so
   a few fields available through Option A are not reconstructed from
   ``SETROPTS LIST`` text. Prefer Option A when you can run the REXX.


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


