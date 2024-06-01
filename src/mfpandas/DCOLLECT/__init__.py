import os 
import pandas as pd 
import datetime 


class DCOLLECT:

 

    def __init__(self, dcollect=None):
        """Initialize our DCOLLECT class.
        Recordlayout from: https://www.ibm.com/docs/en/zos/3.1.0?topic=output-dcollect-record-structure

        Args:
            dcollect (path, required): Path to dcollect file. Defaults to None.
                                       this should be a BINARY received DCOLLECT file
        """

        self._dcolfile = dcollect
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
            }
                       

    def parse_t(self):
        with open(self._dcolfile, 'rb') as fid:
            while True:
                try:
                    DCULENG = int(fid.read(2).hex(),16)
                except:
                    # we must have hit the end of the file :)
                    break
                print('Have a record of',DCULENG,'bytes')
                restrec = fid.read(DCULENG-2)
                DCURCTYP = restrec[2:4].decode('cp500').strip()
                if DCURCTYP == 'D':
                    self._DRECS['DCDDSNAM'].append(restrec[22:66].decode('cp500').strip())
                    DCDERROR = bin(restrec[66])
                    print(DCDERROR)
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
                    else:
                        expdte =  datetime.datetime.strptime(expraw, '%Y%j').date()
                    self._DRECS['DCDEXPDT'].append(expdte)

                    lrraw = restrec[110:114].hex()[0:7]
                    if lrraw == '0000000':
                        lrdte = False
                    else:
                        lrdte = datetime.datetime.strptime(lrraw, '%Y%j').date()
                    self._DRECS['DCDLSTRF'].append(lrdte)

                    #print(DCDFLAG1, bin(DCDFLAG1), DCDRACFD, DCDSMSM,DCDTEMP,DCDPDSE,DCDGDS,DCDREBLK,DCDCHIND,DCDCKDSI )
                    #print(restrec.hex())
                 
                # DCURCTYP = l[4:6].decode('cp500').strip()
                # DCUSYSID = l[8:12].decode('cp500')
                # print(DCURCTYP)
                # if DCURCTYP == 'D':
                #     print(DCURCTYP,DCUSYSID)
                #     DCDDSNAM = l[24:68].decode('cp500').strip()
                #     print(DCDDSNAM)
            self.drecs = pd.DataFrame.from_dict(self._DRECS)



            



