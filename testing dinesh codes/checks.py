import pandas as pd

df=pd.read_excel(r"C:\Users\dinesh.verma\Downloads\DamageCodeDAtaLoad.xls")

df=df.rename(columns={
    'RecordTypeName': 'RecordType.name'})

print(df.columns)

print(df.head(5))