Installing MFPandas
###################

Installing MFPandas is easily done via pip::

     mkdir mystuff
     cd mystuff
     pyhton -m venv venv
     . venv/bin/activate
     pip install mfpandas

Installing MFPandas on z/OS
###########################

`Jørn Thyssen <https://www.linkedin.com/in/j%C3%B8rn-thyssen-7b94784>`_ figured out a way to run MFPandas natively on z/OS. Assuming you've
python already installed follow these steps::

    mkdir mystuff
    cd mystuff
    python3 -m venv venv 
    . venv/bin/activate
    pip3 install pip --upgrade
    pip3 install xlsxwriter
    pip3 install --index-url https://downloads.pyaitoolkit.ibm.net/repository/python_ai_toolkit_zos/simple --trusted-host downloads.pyaitoolkit.ibm.net --only-binary :all: pandas
    pip3 install --index-url https://downloads.pyaitoolkit.ibm.net/repository/python_ai_toolkit_zos/simple --trusted-host downloads.pyaitoolkit.ibm.net --only-binary :all: python-dateutil
    pip3 install --index-url https://downloads.pyaitoolkit.ibm.net/repository/python_ai_toolkit_zos/simple --trusted-host downloads.pyaitoolkit.ibm.net --only-binary :all: pytz
    pip3 install –no-deps mfpandas

See the IBM `https://www.ibm.com/docs/en/daefz/1.1.0?topic=feature-installing-required-python-packages <documentation>`_ for more infomation on the 'special' pandas install...




