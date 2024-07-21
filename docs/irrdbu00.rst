Working with IRRDBU00 data
##########################

The :doc:`IRRDBU00 Class <irrdbu00class>` is made to work with IRRDBU00 data. 
It will give you methods to get:

  - *standard dataframes*: strict conversion of IRRDBU00 recordtypes to Pandas DataFrames
  - *augmented dataframes*: like standard dataframes but with extra columns added
  - *specialised dataframes*: preselected queries we all want to do on our RACF
  - *handy add-ons*: extra query features, data structures, xlsx-generation etc.





Standard DataFrames
*******************

Below you will see one of the core pieces of code of the parsing stucture.
The 'key' of the dictionary (0100, 0101, etc.) is the recordtype from the IRRDBU00 unload as described in https://www.ibm.com/docs/en/zos/3.1.0?topic=records-irrdbu00-record-types. 

If, for instance, we're looking at the "Group Basic Data" in recordtype ``0100`` you'll see an 'interal name' of ``GPBD`` and a 'dataframe name' of ``_groups``.
This means the resulting Pandas DataFrame is available, after parsing as ``.groups``.


.. literalinclude:: ../src/mfpandas/irrdbu00.py
   :language: python
   :lines: 174-279
   :linenos:


The Standard DataFrames look 'just like the documentation'. For example, the '0100'-records are parsed then available via the ``.groups`` method of the IRRDBU00 class.
It will have all the fields as documented at https://www.ibm.com/docs/en/zos/3.1.0?topic=records-record-formats-produced-by-database-unload-utility#idg63092__title__1 

Here's the output of the ``.groups.info()`` call on a fully parsed unload::

    >>> r.groups.info()
    <class 'pandas.core.frame.DataFrame'>
    Index: 11332 entries, $AAAA to Z$FGRP01
    Data columns (total 10 columns):
    #   Column             Non-Null Count  Dtype 
    ---  ------             --------------  ----- 
    0   GPBD_RECORD_TYPE   23991 non-null  object
    1   GPBD_NAME          23991 non-null  object
    2   GPBD_SUPGRP_ID     23991 non-null  object
    3   GPBD_CREATE_DATE   23991 non-null  object
    4   GPBD_OWNER_ID      23991 non-null  object
    5   GPBD_UACC          23991 non-null  object
    6   GPBD_NOTERMUACC    23991 non-null  object
    7   GPBD_INSTALL_DATA  23991 non-null  object
    8   GPBD_MODEL         23991 non-null  object
    9   GPBD_UNIVERSAL     23991 non-null  object


Augmented DataFrames
********************
.. .. autoclass:: mfpandas.IRRDBU00
..     :members: 
..     :private-members:
..     :special-members:
..     :noindex:

Specialised DataFrames
**********************

Handy add-ons
*************

Examples
********

You need to get a report of all the users on the system that are still don't have a passphrase.
===============================================================================================

First you create an ``IRRDBU00``-unload via the following JCL::

    //UNLOAD   EXEC PGM=IRRDBU00,PARM=NOLOCKINPUT               
    //SYSPRINT DD   SYSOUT=*                                    
    //INDD1    DD   DISP=SHR,DSN=SYS1.BACKUP                     
    //OUTDD    DD   DSN=HLQ.TO.UNLOAD.FILE,                   
    //              DISP=(,CATLG,DELETE),                       
    //              SPACE=(CYL,(100,150)),                        
    //              DCB=(RECFM=VB,LRECL=4096,BLKSIZE=20480)   

After submitting the above JCL, you transfer the ``HLQ.TO.UNLOAD.FILE`` (ASCII) to your Linux box (currently mfpandas does not run on z/OS, due to Pandas not working nicely on z/OS yet...)

Once the file is receieved you create a folder for your work and install the mfpandas library like below::

    henri@linux-box:~/$ mkdir my_cool_project
    henri@linux-box:~/$ cd my_cool_project
    henri@linux-box:~/my_cool_project$ python -m venv virtualenv
    (virtualenv) henri@linux-box:~/my_cool_project$ pip install mfpandas
    (virtualenv) henri@linux-box:~/my_cool_project$ cp ~/Downloads/HLQ.TO.UNLOAD.FILE irrdbu00 

Now, just for a quick and dirty result you enter an interactive python terminal and::

    >>> from mfpandas import IRRDBU00
    >>> racf = IRRDBU00(irrdbu00='/home/henri/irrdbu00')
    >>> racf.parse_fancycli(recordtypes=['0200'])
    24-07-01 20:35:15 - parsing /home/henri/irrdbu00
    24-07-01 20:35:23 - progress: ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉                      (26.98%)

After parsing is finished can start interactively coding the solution::

    24-07-01 20:35:51 - total parse time: 47.209619 seconds
    >>> users_without_phrase = racf.users.loc[racf.users.USBD_PHR_ALG=='NOPHRASE']
    >>> for user in users_without_phrase['USBD_NAME'].values:
    ...   print(f'User {user} is still not using a passphrase')
    ...
    User IBMUSER is still not using a passphrase
    User TEST001 is still not using a passphrase
    User TEST002 is still not using a passphrase
    >>>

As you can see above, with some relatively easy to learn 'Pandas Queries' (https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.loc.html), using the standard IBM labelnames 
you can quickly het some results. It's a small feat to then extend that code with some 'RACF COMMAND GENERATION' to 
give all these users a new 'one time' passphrase they must change after first logon with said passphrase::

    >>> cmds = []
    >>> for user in users_without_phrase['USBD_NAME'].values:
    ...   print(f'User {user} is still not using a passphrase')
    ...   commands.append(f'ALU {user} PRASE('mfpandas_gave_me_a_passphrase'))
    ...
    >>> with open('/givethemprases.txt') as f:
    ...   f.writelines(commands)

After which you can easily stick that on the end of an ``IKJEFT01`` to execute the commands.