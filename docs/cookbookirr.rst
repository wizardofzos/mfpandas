Cookbook IRRDBU00
=================

Here you'll see some examples of working with the IRRDBU00 class.

Before we can start working with an IRRDBU00 file, we first need to create one. 
head on over to your favourite operating system (z/OS) and submit a job like the following::

        //UNLOAD   EXEC PGM=IRRDBU00,PARM=NOLOCKINPUT
        //SYSPRINT   DD SYSOUT=*
        //INDD1    DD   DISP=SHR,DSN=PATH.TO.YOUR.RACFDB
        //OUTDD    DD   DISP=(,CATLG,DELETE),
        //              DSN=YOUR.IRRDBU00.FILE,
        //              DCB=(RECFM=VB,LRECL=4096),
        //              SPACE=(CYL,(50,150),RLSE)

For more information on the IRRDBU00-utility please refer to the `IBM Documenation <https://www.ibm.com/docs/en/zos/3.1.0?topic=database-using-racf-unload-utility-irrdbu00>`_

For all examples here we're assuming you've already ran the following code::

    from mfpandas import IRRDBU00
    import time

    r = IRRDBU00('/path/to/irrdbu00-unload')
    r.parse()
    while r.status['status'] != 'Ready':
        time.sleep(1)


Let's find all special users and their last logon date::

    >>>r.specials[['USBD_NAME','USBD_LASTJOB_DATE']]
            USBD_NAME USBD_LASTJOB_DATE
    5491    IBMUSER         1984-12-15
    5830    EMERG01         2024-01-05







