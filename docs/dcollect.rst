Working with DCOLLECT data
==========================

The :py:class:`mfpandas.DCOLLECT` is made to work with DCOLLECT data.

DCOLLECT Examples
*****************

Here you'll see some examples of working with the DCOLLECT class.

For all examples here we're assuming you've already ran the following code::

    from mfpandas import DCOLLECT
    import time

    d = DCOLLECT('/path/to/dcolfile')
    d.parse()
    while d.status['status'] not in ('Ready', 'Error'):
        time.sleep(1)

    if d.status['status'] == 'Error':
        raise RuntimeError(d.status['error'])


To find all datasets starting with 'SYS1' and the volulme they're on::

    >>> d.datasets.loc[d.datasets.DCDDSNAM.str.startswith('SYS1')][['DCDDSNAM', 'DCDVOLSR']]
                          DCDDSNAM DCDVOLSR
    0            SYS1.VVDS.VSARES1   SARES1
    3      SYS1.S0W1.STGINDEX.DATA   SARES1
    4     SYS1.S0W1.STGINDEX.INDEX   SARES1
    5          SYS1.S0W1.MAN1.DATA   SARES1
    6          SYS1.S0W1.MAN2.DATA   SARES1
    ...                        ...      ...
    6107        SYS1.VTOCIX.ZDO002   ZDO002
    6108         SYS1.VVDS.VZDO003   ZDO003
    6458        SYS1.VTOCIX.ZDO003   ZDO003
    6459         SYS1.VVDS.VZDO004   ZDO004
    6703        SYS1.VTOCIX.ZDO004   ZDO004


To find all datasets on a volume::

    >>> d.datsets_on_volume(volser='A5DBAR')
    ['SYS1.VTOCIX.A5DBAR', 'SYS1.VVDS.VA5DBAR']


Missing dates and encryption information
****************************************

Packed DCOLLECT dates containing zero or invalid values are returned as
``None`` rather than terminating the background parser. Before 0.1.8 these
were returned as ``False``, so replace any ``== False`` filters on
``DCDCREDT``, ``DCDEXPDT`` or ``DCDLSTRF`` with ``.isnull()``.

Dataset records also expose ``DCDATYPE`` and ``DCDAKLBL``. ``DCDATYPE`` is
``0100`` for AES-256 XTS encryption and ``FFFF`` for an unencrypted data set;
``DCDAKLBL`` holds the key label and is blank for unencrypted data sets. Both
are empty for D-records written before APAR OA51067, which are too short to
contain them.


VSAM associations
*****************

The ``associations`` property exposes parsed type-A records. ``DCADSNAM`` is
the component data set and ``DCAASSOC`` is its associated base cluster. The
``DCAKSDS``, ``DCAESDS``, ``DCARRDS``, and ``DCALDS`` Boolean columns describe
the VSAM organization.



