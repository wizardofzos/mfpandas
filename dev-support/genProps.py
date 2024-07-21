import json

with open('src/mfpandas/irrdbu00-offsets.json') as j:
    offsets = json.load(j)

# copy paste recrodtype_info from irrdbu00.py here
_recordtype_info = {
    '0100': {'name':'GPBD', 'df':'_groups'},
    '0101': {'name':'GPSGRP', 'df':'_subgroups'},
    '0102': {'name':'GPMEM', 'df':'_connects'},
    '0103': {'name':'GPINSTD', 'df':'_groupUSRDATA'},
    '0110': {'name':'GPDFP', 'df':'_groupDFP'},
    '0120': {'name':'GPOMVS', 'df':'_groupOMVS'},
    '0130': {'name':'GPOVM', 'df':'_groupOVM'},
    '0141': {'name':'GPTME', 'df':'_groupTME'},
    '0151': {'name':'GPCSD', 'df':'_groupCSDATA'},
    '0200': {'name':'USBD', 'df':'_users'},
    '0201': {'name':'USCAT', 'df':'_userCategories'},
    '0202': {'name':'USCLA', 'df':'_userClasses'},
    '0203': {'name':'USGCON', 'df':'_groupConnect'},
    '0204': {'name':'USINSTD', 'df':'_userUSRDATA'}, 
    '0205': {'name':'USCON', 'df':'_connectData'},
    '0206': {'name':'USRSF', 'df':'_userRRSFdata'},
    '0207': {'name':'USCERT', 'df':'_userCERTname'},
    '0208': {'name':'USNMAP', 'df':'_userAssociationMapping'},
    '0209': {'name':'USDMAP', 'df':'_userDistributedIdMapping'},  
    '020A': {'name':'USMFA', 'df':'_userMFAfactor'},
    '020B': {'name':'USMPOL', 'df':'_userMFApolicies'},
    '0210': {'name':'USDFP', 'df':'_userDFP'},
    '0220': {'name':'USTSO', 'df':'_userTSO'},
    '0230': {'name':'USCICS', 'df':'_userCICS'},
    '0231': {'name':'USCOPC', 'df':'_userCICSoperatorClasses'},
    '0232': {'name':'USCRSL', 'df':'_userCICSrslKeys'},
    '0233': {'name':'USCTSL', 'df':'_userCICStslKeys'},
    '0240': {'name':'USLAN', 'df':'_userLANGUAGE'},
    '0250': {'name':'USOPR', 'df':'_userOPERPARM'},
    '0251': {'name':'USOPRP', 'df':'_userOPERPARMscope'},
    '0260': {'name':'USWRK', 'df':'_userWORKATTR'},
    '0270': {'name':'USOMVS', 'df':'_userOMVS'},
    '0280': {'name':'USNETV', 'df':'_userNETVIEW'},
    '0281': {'name':'USNOPC', 'df':'_userNETVIEWopclass'},
    '0282': {'name':'USNDOM', 'df':'_userNETVIEWdomains'},
    '0290': {'name':'USDCE', 'df':'_userDCE'},
    '02A0': {'name':'USOVM', 'df':'_userOVM'},
    '02B0': {'name':'USLNOT', 'df':'_userLNOTES'},
    '02C0': {'name':'USNDS', 'df':'_userNDS'},
    '02D0': {'name':'USKERB', 'df':'_userKERB'},
    '02E0': {'name':'USPROXY', 'df':'_userPROXY'},
    '02F0': {'name':'USEIM', 'df':'_userEIM'},
    '02G1': {'name':'USCSD', 'df':'_userCSDATA'},
    '1210': {'name':'USMFAC', 'df':'_userMFAfactorTags'},
    '0400': {'name':'DSBD', 'df':'_datasets'},
    '0401': {'name':'DSCAT', 'df':'_datasetCategories'},
    '0402': {'name':'DSCACC', 'df':'_datasetConditionalAccess'},
    '0403': {'name':'DSVOL', 'df':'_datasetVolumes'},
    '0404': {'name':'DSACC', 'df':'_datasetAccess'},
    '0405': {'name':'DSINSTD', 'df':'_datasetUSRDATA'},
    '0406': {'name':'DSMEM', 'df':'_datasetMember'},
    '0410': {'name':'DSDFP', 'df':'_datasetDFP'},
    '0421': {'name':'DSTME', 'df':'_datasetTME'},
    '0431': {'name':'DSCSD', 'df':'_datasetCSDATA'},
    '0500': {'name':'GRBD', 'df':'_generals'},
    '0501': {'name':'GRTVOL', 'df':'_generalTAPEvolume'},
    '0502': {'name':'GRCAT', 'df':'_generalCategories'},
    '0503': {'name':'GRMEM', 'df':'_generalMembers'},
    '0504': {'name':'GRVOL', 'df':'_generalTAPEvolumes'},
    '0505': {'name':'GRACC', 'df':'_generalAccess'},
    '0506': {'name':'GRINSTD', 'df':'_generalUSRDATA'},
    '0507': {'name':'GRCACC', 'df':'_generalConditionalAccess'},
    '0508': {'name':'GRFLTR', 'df':'_generalDistributedIdFilter'},
    '0509': {'name':'GRDMAP', 'df':'_generalDistributedIdMapping'},
    '0510': {'name':'GRSES', 'df':'_generalSESSION'},
    '0511': {'name':'GRSESE', 'df':'_generalSESSIONentities'},
    '0520': {'name':'GRDLF', 'df':'_generalDLFDATA'},
    '0521': {'name':'GRDLFJ', 'df':'_generalDLFDATAjobnames'},
    '0530': {'name':'GRSIGN', 'df':'_generalSSIGNON'}, 
    '0540': {'name':'GRST', 'df':'_generalSTDATA'},
    '0550': {'name':'GRSV', 'df':'_generalSVFMR'}, 
    '0560': {'name':'GRCERT', 'df':'_generalCERT'},
    '1560': {'name':'CERTN', 'df':'_generalCERTname'},
    '0561': {'name':'CERTR', 'df':'_generalCERTreferences'},
    '0562': {'name':'KEYR', 'df':'_generalKEYRING'},
    '0570': {'name':'GRTME', 'df':'_generalTME'},
    '0571': {'name':'GRTMEC', 'df':'_generalTMEchild'},
    '0572': {'name':'GRTMER', 'df':'_generalTMEresource'},
    '0573': {'name':'GRTMEG', 'df':'_generalTMEgroup'},
    '0574': {'name':'GRTMEE', 'df':'_generalTMErole'},
    '0580': {'name':'GRKERB', 'df':'_generalKERB'},
    '0590': {'name':'GRPROXY', 'df':'_generalPROXY'},
    '05A0': {'name':'GREIM', 'df':'_generalEIM'},
    '05B0': {'name':'GRALIAS', 'df':'_generalALIAS'}, 
    '05C0': {'name':'GRCDT', 'df':'_generalCDTINFO'},
    '05D0': {'name':'GRICTX', 'df':'_generalICTX'},
    '05E0': {'name':'GRCFDEF', 'df':'_generalCFDEF'},
    '05F0': {'name':'GRSIG', 'df':'_generalSIGVER'},
    '05G0': {'name':'GRCSF', 'df':'_generalICSF'},
    '05G1': {'name':'GRCSFK', 'df':'_generalICSFsymexportKeylabel'},
    '05G2': {'name':'GRCSFC', 'df':'_generalICSFsymexportCertificateIdentifier'},
    '05H0': {'name':'GRMFA', 'df':'_generalMFA'},
    '05I0': {'name':'GRMFP', 'df':'_generalMFPOLICY'},
    '05I1': {'name':'GRMPF', 'df':'_generalMFPOLICYfactors'},
    '05J1': {'name':'GRCSD', 'df':'_generalCSDATA'},
    '05K0': {'name':'GRIDTP', 'df':'_generalIDTFPARMS'},
    '05L0': {'name':'GRJES', 'df':'_generalJES'}
    }

for d in offsets:
  print('@property')
  rtype = offsets[d]['record-type']
  df = _recordtype_info[rtype]['df']
  print(f'def {df.lstrip("_")}(self):')
  print(f'    """Returns a DataFrame for the {d.replace("-"," ")}')
  print(f'    More information: {offsets[d]["ref-url"]}')
  fields = []
  descs = []
  for field in offsets[d]['offsets']:
        fields.append(field["field-name"])
        descs.append(field["field-desc"])
  # let longests
  maxf = maxd = 0
  for field in fields:
      if len(field) > maxf:
          maxf = len(field)
  for desc in descs:
      if len(desc) > maxd:
          maxd = len(desc)
  print('')
  print(f'    {maxf*"="} {maxd*"="}')
  print(f'    Column{(maxf-6)*" "} Description')
  print(f'    {maxf*"="} {maxd*"="}')
  for i,f in enumerate(fields):
      print(f'    {f}{(maxf-len(f))*" "} {descs[i]}')
  print(f'    {maxf*"="} {maxd*"="}')
  print('')

  print(f'    """')

  print(f'    return self.{df}')
  print('')