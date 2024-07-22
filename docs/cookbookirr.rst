Cookbook IRRDBU00
=================

Here you'll see some examples of working with the IRRDBU00 class.

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







