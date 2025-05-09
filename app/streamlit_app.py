import streamlit as st
import pandas as pd
from datetime import datetime,timedelta
from currency_converter import CurrencyConverter
import hashlib

cc = CurrencyConverter()

# def CurrencyConvertCalc(used_currency,settlement_currency_code,date='Today'):
#     # based on currency_converter https://pypi.org/project/CurrencyConverter/
#     if date=='Today':
#         return cc.convert(1,used_currency,settlement_currency_code)
#     else:
#         return cc.convert(1,used_currency,settlement_currency_code,date)

import requests
from bs4 import BeautifulSoup as bs
financial_data_source,fds_link='Google','https://www.google.com/finance'
fds_markout='<h5><i>Financial Data Source: <a href="%s" target="_blank">%s</a></i></h5>'%(fds_link,financial_data_source)
def CurrencyConvertCalc(used_currency,settlement_currency_code,date='Today'):
    if date!='Today':
        return 1
    webpage = requests.get('https://www.google.com/finance/quote/%s-%s'%(used_currency,settlement_currency_code)).text
    soup=bs(webpage, "html.parser")
    cr=soup.find('div',{'class':'fxKbKc'}).text #currency rate
    cr=float(cr)
    print('[log] load from google')
    return cr


#init ISO4217
iso4217_data=pd.read_csv('ISO4217.csv')
iso4217_list=(iso4217_data.code+' '+iso4217_data.name).to_list()

# def iso4217noted(iso4217code):
#     return iso4217code+' '+iso4217_data[iso4217_data.code==iso4217code].name.iloc[0]

def budget_gene(budget_name):
    budget_file='bills/'+budget_name+'.csv'
    # init streamlit
    st_left,st_right=st.columns((1,3))

    # init expenses records
    er_data=pd.read_csv(budget_file,index_col='date')
    er_data.index=pd.to_datetime(er_data.index,format="%Y%m%d")

    st_right.write("账单明细：")

    new_er_data=st_right.data_editor(
        er_data
        ,use_container_width=True
        ,num_rows="dynamic"
        ,column_config={
            "date": st.column_config.DatetimeColumn(
                "日期",
                format="D MMM YYYY",
            ),
            "items": "项目",
            "price": st.column_config.NumberColumn(
                "价格",
                format="%.2f"
            ),
            "currency": st.column_config.SelectboxColumn(
                "币种",
               #  width="medium",
                options=iso4217_list,
            ),
            "debtor": "应付人",#debtor
            "creditor": "付款人"#creditor
        }
    )

    #init people
    debtor=er_data.creditor.to_list()
    for p in [debtors.split(' ') for debtors in er_data.debtor.to_list()]:
        debtor+=p
    peoples=sorted(list(set(debtor)))

    trading_currencies=er_data.currency.value_counts().index.to_list()
    common_currency=["CNY 人民币元","HKD 港元","USD 美元"]
    iso4217_list_rearranged=common_currency+list(set(trading_currencies)-set(common_currency))  +list(set(iso4217_list)-set(common_currency)-set(trading_currencies))

    settlement_currency = st_left.selectbox(
        '结算币种：',
        iso4217_list_rearranged)

    used_currencies=list(set(trading_currencies)-set([settlement_currency]))

    used_currencies_codes=[code[0:3] for code in used_currencies]
    settlement_currency_code=settlement_currency[0:3]

    rates_compare=pd.DataFrame(index=used_currencies_codes,columns=['x/sc_code','sc_code/x',    'trend'])
    # rates_compare=pd.DataFrame(index=used_currencies_codes,columns=['x/'  +settlement_currency_code,settlement_currency_code+'/x','trend(x/%s)  '%settlement_currency_code])
    for uc_code in used_currencies_codes:
        rates_compare.loc[uc_code,'x/sc_code']=CurrencyConvertCalc(uc_code,settlement_currency_code)
        hist_data=[]
        for shift_date in range(30):
            date=(datetime.today()-timedelta(days=shift_date))
            try:
                hist_currency_rate=CurrencyConvertCalc(uc_code,settlement_currency_code,date)
                hist_data.append(hist_currency_rate)
            except:
                continue
        rates_compare.loc[uc_code,'trend']=sorted(hist_data,reverse=True)
    rates_compare['sc_code/x']=1/rates_compare['x/sc_code']

    bill_detail=er_data.copy()

    need_currency_convert=(not len(used_currencies_codes) == 0)
    if need_currency_convert:        
        
        bill_detail['converted price(%s)'%settlement_currency_code]=0

        st_left.write("近期汇率：")
        st_left.dataframe(
            rates_compare
            ,use_container_width=True
            ,column_config={
                'x/sc_code':'x/'+settlement_currency_code,
                'sc_code/x':settlement_currency_code+'/x',
                'trend':st.column_config.LineChartColumn(
                    'trend(x/%s)(last 1 month)'%settlement_currency_code
                )
            }
        )
        st_left.html(fds_markout)
        

    # share money
    ledger={}
    for date,item_detail in er_data.iterrows():
        # print(item_detail)
        # break
        price_convert=cc.convert(item_detail.price,item_detail.currency[0:3],   settlement_currency_code)
        if need_currency_convert:
            bill_detail.loc[date,'converted price(%s)'%settlement_currency_code]=price_convert
        debtors=item_detail.debtor.split(' ')
        creditor=item_detail.creditor
        shares=len(debtors)
        ppp=price_convert/shares #price per portion
        for debtor in debtors:
            # print(debtor,creditor)
            if debtor==creditor:
                continue
            if "%s2%s"%(debtor,creditor) in ledger.keys():
                ledger["%s2%s"%(debtor,creditor)]+=ppp
                bill_detail.loc[date,"%s2%s"%(debtor,creditor)]=+ppp
            elif "%s2%s"%(creditor,debtor) in ledger.keys():
                ledger["%s2%s"%(creditor,debtor)]-=ppp
                bill_detail.loc[date,"%s2%s"%(creditor,debtor)]=-ppp
            else:
                ledger["%s2%s"%(debtor,creditor)]=ppp
                bill_detail.loc[date,"%s2%s"%(debtor,creditor)]=ppp
    
    ledger_hori=pd.DataFrame(ledger, index=['price'])
    ledger=ledger_hori.T
    bill_detail=bill_detail.fillna(0).round(2)
    bill_detail.index=bill_detail.index.strftime('%Y%m%d')
    bill_detail.loc['SUM'] = ['']*bill_detail.shape[1]
    bill_detail.loc['SUM',ledger_hori.columns]=ledger_hori.iloc[0].round(2)

    # print(ledger)
    for transfer,price in ledger.iterrows():
        # print(transfer)
        person_a,person_b=transfer.split('2')
        if price['price']>0:
            ledger.rename(index={transfer:"%s应转%s"%(person_a,person_b)}, inplace=True)
            bill_detail.rename(columns={transfer:"%s应转%s"%(person_a,person_b)}, inplace=True)
        elif price['price']<0:
            ledger.loc[transfer,'price']=-ledger.loc[transfer,'price']
            ledger.rename(index={transfer:"%s应转%s"%(person_b,person_a)}, inplace=True)
            bill_detail[transfer]=-bill_detail[transfer]
            bill_detail.rename(columns={transfer:"%s应转%s"%(person_b,person_a)}, inplace=True)
        else:
            ledger.drop(transfer)

    st_left.dataframe(
        ledger
        ,use_container_width=True
        ,column_config={
            'price':st.column_config.NumberColumn(
                "应转金额（%s）"%settlement_currency_code
                ,format="%s "%settlement_currency_code+"%.2f"
            )
        }
    )
    
    def renew_bill():
        new_er_data.index=new_er_data.index.strftime('%Y%m%d')
        if new_er_data.isna().any().any():
            return 0
        new_er_data.to_csv(budget_file)

    @st.cache_data
    def convert_df(df):
        return df.to_csv().encode('gbk')
    bill_detail_csv=convert_df(bill_detail)

    action_buttons=st_right.columns(8)


    action_buttons[0].button('更新账单🔄',on_click=renew_bill)
    action_buttons[1].download_button(
        "下载账单⏬",
        bill_detail_csv,
        "%s.csv"%budget_name,
        "text/csv",
        key='download-csv'
    )

def welcome_page():
    st.html("<h1>Welcome! 👋</h1>")
    st.html("<h3>👈Please select a bill from side bar to start!</h3>")

def error_page():
    st.html("<h1>Something Wrong with this Bill!</h1>")
    st.html("<h3>Please refresh the page or contact the administrator for help!</h3>")

def passwd_error_page():
    st.html("<h1>Password Incorrect!</h1>")
    st.html("<h3>Please try again or contact the administrator for help!</h3>")

def verify_password(bill_name,password, hashed_password,encrypt_mode=False):
    salt=bill_name.encode('utf-8')
    new_hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()
    if encrypt_mode: # send any values to hashed_password when using encrypt mode
        return new_hashed_password
    else:
        return new_hashed_password == hashed_password

bills_and_passwds_all=pd.read_csv('bills_passwd.csv')
bills_and_passwds=bills_and_passwds_all[bills_and_passwds_all.visible==1]

bills_alias=bills_and_passwds.alias.to_list()
st.set_page_config(page_title='账单',layout="wide")
st.sidebar.title('')

selection_alias = st.sidebar.selectbox("Bills", bills_alias)
selection = bills_and_passwds_all[bills_and_passwds_all.alias==selection_alias].bills.iloc[0]
passwd = st.sidebar.text_input('Password', value="",type="password")
# print(bills_and_passwds[bills_and_passwds.bills==selection].passwd.iloc[0])
hashed_password=bills_and_passwds[bills_and_passwds.bills==selection].passwd.iloc[0]
if verify_password(selection,passwd, hashed_password):
    try:
        budget_gene(selection)
    except:
        pass
        # error_page()
else:
    welcome_page()
    st.sidebar.markdown('👆 :red[*please input password*]')

# if st.sidebar.button('load bill'):
#     if verify_password(selection,passwd, hashed_password):
#         try:
#             budget_gene(selection)
#         except:
#             error_page()
#     else:
#         st.sidebar.markdown(':red[*Password incorrect!*]')
#         passwd_error_page()
# else:
#     welcome_page()

