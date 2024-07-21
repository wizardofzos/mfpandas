The mfpandas library
====================


Why
***

The z/OS operating system exports a variety of different data into datasets.
Traditionally these would be used inside a ``DFSort`` or ``ICETOOL`` job to query this information and generate insightful reports based on this data.

With mfpanas you can do the same, but with the power of python.

The various mfpandas classes will give you the tools to convert these 'tradtional' Mainframe Datasets into Pandas DataFrames.

This library is not intended to cover all reporting requirements (as that would be crazy and too complex to suit everybodies needs) instead
it focusses on generating Pandas Datasets that contain all the information from the Mainframe Datasets so you can build your own tools 
on top of it.

Currently available classes

  - :doc:`IRRDBU00 <irrdbu00class>` 
  - :doc:`DCOLLECT <dcollectclass>` 

History
*******

Initially, there was only "pyracf," a Python parser designed for IRRDBU00 unloads. You can find that outdated repository at https://github.com/wizardofzos/pyracf. However, I discovered another project named "pyracf" (https://github.com/ambitus/pyracf) that now cannot use the name on pypi.org. We discussed merging the two pyracf projects, but this was unsuccessful primarily because their pyracf was intended to run on z/OS, while mine was not.

Driven by the need for more Pythonic ways to handle "Mainframe Things," I decided to pivot to creating mfpandas, a dedicated framework for parsing Mainframe Data into Pandas DataFrames. This shift offers several benefits: it allows for more mainframe parsing capabilities within a single pip install and frees up the pyracf name for ambitus's pyracf project.
You'll notice some of the orgininal 'pyracf methods' are missing from the new IRRDBU00-class. This is because they need a good rewrite due to the new setup of the class (mainly documentation related).











