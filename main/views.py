from django.shortcuts import render, redirect
import json
import queue
import threading
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import time
from datetime import datetime, timedelta
import urllib
from requests_html import HTML, HTMLSession
from yahooquery import Ticker
from babel.numbers import format_currency
from numerize.numerize import numerize
from numpy import sqrt, arctan, pi

def search(request):
    return render(request, 'main/search.html')

def convert(request, s):
    try:
        def google_results(query):
            def get_source(url):
                try:
                    session = HTMLSession()
                    response = session.get(url)
                    return response

                except requests.exceptions.RequestException as e:
                    print(e)

            def get_results(query):  
                query = urllib.parse.quote_plus(query)
                response = get_source("https://www.google.com/search?q=" + query)
                return response

            def parse_results(response):
                css_identifier_result = ".tF2Cxc"
                css_identifier_title = "h3"
                css_identifier_link = ".yuRUbf a"
                css_identifier_text = ".VwiC3b"
                results = response.html.find(css_identifier_result)
                output = []
                for result in results:
                    item = {
                        'title': result.find(css_identifier_title, first=True).text,
                        'link': result.find(css_identifier_link, first=True).attrs['href'],
                        'text': result.find(css_identifier_text, first=True).text
                    }
                    output.append(item)
                return output

            def google_search(query):
                query = "site:finance.yahoo.com/quote " + query
                response = get_results(query)
                results = parse_results(response)
                i = results[1]['link']
                ii = i.split('/')[4]
                return ii
            return google_search(query)
        ticker = google_results(s)
        return redirect('main', t=ticker)
    except:
        return redirect('not-found')

def main(request, t):
    try:
        tkr = t
        def MacroData(first, second):
            url=f"https://www.macrotrends.net/stocks/charts/{tkr}/tesla/{first}"
            html_data = requests.get(url).text
            soup = BeautifulSoup(html_data, "html5lib")
            dictt = {}
            tables = soup.find_all("table", attrs={"class":"historical_data_table table"})
            for table in tables:
                if second in table.find("th").getText():
                    for row in table.find("tbody").find_all("tr"):
                        col = row.find_all("td")
                        if (col != [2] ):
                            date = col[0].text
                            data = col[1].text.replace("$", "").replace(",", "")
                            dictt[date] = data
            return dictt

        def YahooData(first, second):
            url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{tkr}?modules={first}'
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
            result = requests.get(url, headers=headers).json()['quoteSummary']['result'][0][first][second]
            return result

        def SharesOutstanding():
            url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{tkr}?modules=price'
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
            result = requests.get(url, headers=headers).json()['quoteSummary']['result'][0]["price"]
            data = int(result["marketCap"]['raw'] / result["regularMarketPrice"]['raw'])
            return data

        def Name(q):
            try:
                data = BeautifulSoup(requests.get(f"https://www.macrotrends.net/stocks/charts/{tkr}/apple/revenue").text, "html5lib").find("h2").text.split('Revenue')[0][:-1]
            except:
                data = Ticker(tkr).quote_type[tkr]["longName"].split(',')[0]
            q.put_nowait(data)

        def stock_data():
            dictt = MacroData('revenue', 'Annual Revenue')
            ticker = yf.Ticker(tkr)
            info = ticker.history(period = "10Y")
            stock_prices = info.to_dict()['Close']
            dictionary = {i:stock_prices[i] for i in stock_prices}
            shares = SharesOutstanding()

            if len(dict(list(dict(filter(lambda x:x[1], dictt.items())).items()))) == 0:
                result = YahooData('incomeStatementHistory', 'incomeStatementHistory')

                previous_year = str(result[1]['endDate']['fmt'].split('-')[0])
                this_year = str(list(dictionary.keys())[-1]).split(' ')[0]
                timestamp = int(time.mktime(datetime.strptime(this_year, "%Y-%m-%d").timetuple())) * 1000 - 31540000000
            else:
                previous_year = str(int(str(list(dictionary.keys())[0]).split('-')[0])-1)
                this_year = str(list(dictionary.keys())[0]).split(' ')[0]
                timestamp = int(time.mktime(datetime.strptime(this_year, "%Y-%m-%d").timetuple())) * 1000
            dat = {k:v for k, v in {int(i.timestamp() * 1000):stock_prices[i] for i in stock_prices}.items() if k > timestamp}
            sd = dat
            data = {i:float("%.2f" %(int(sd[i]*shares)/1000000000)) for i in sd}
            return [previous_year, this_year, timestamp, data, sd]
        stock_data = stock_data()


        def annual_revenue():
            dictt = MacroData('revenue', 'Annual Revenue')
            timestamp = int(time.mktime(datetime.strptime(stock_data[0], "%Y").timetuple())) * 1000
            test = dict(reversed(list(dict(filter(lambda x:x[1], dictt.items())).items())))
            if len(test) == 0:
                result = YahooData('incomeStatementHistory', 'incomeStatementHistory')
                dic = {}
                for i in range(2):
                    try:
                        dic[result[i]['endDate']['raw']] = str(result[i]['totalRevenue']['raw'])[:-6]
                    except:
                        dic[result[i]['endDate']['raw']] = ''
                dt = dict(reversed(list(dict(dic).items())))
                data = {k:v for k, v in {(i * 1000):int(dt[i]) for i in dt}.items() if k > timestamp}
            else:
                dt = test
                data = {k:v for k, v in {(int(time.mktime(datetime.strptime(i, "%Y").timetuple())) * 1000 + 31495000000):int(dt[i]) for i in dt}.items() if k > timestamp}
            return data

        def annual_net_income():
            dictt = MacroData('net-income', 'Annual Net Income')
            timestamp = int(time.mktime(datetime.strptime(stock_data[0], "%Y").timetuple())) * 1000
            test = dict(reversed(list(dict(filter(lambda x:x[1], dictt.items())).items())))
            if len(test) == 0:
                result = YahooData('incomeStatementHistory', 'incomeStatementHistory')
                dic = {}
                for i in range(2):
                    try:
                        dic[result[i]['endDate']['raw']] = str(result[i]['netIncome']['raw'])[:-6]
                    except:
                        dic[result[i]['endDate']['raw']] = ''
                dt = dict(reversed(list(dict(filter(lambda x:x[1], dic.items())).items())))
                data = {k:v for k, v in {(i * 1000):int(dt[i]) for i in dt}.items() if k > timestamp}
            else:
                dt = test
                data = {k:v for k, v in {(int(time.mktime(datetime.strptime(i, "%Y").timetuple())) * 1000 + 31495000000):int(dt[i]) for i in dt}.items() if k > timestamp}
            return data

        def quarterly_equity():
            dictt = MacroData('total-share-holder-equity', 'Quarterly Share Holder Equity')
            timestamp = stock_data[2] - 9162400000
            test = dict(reversed(list(dict(filter(lambda x:x[1], dictt.items())).items())))
            if len(test) == 0:
                result = YahooData('balanceSheetHistoryQuarterly', 'balanceSheetStatements')
                dic = {}
                for i in range(len(result)):
                    try:
                        dic[result[i]['endDate']['raw']] = str(result[i]['totalStockholderEquity']['raw'])[:-6]
                    except:
                        dic[result[i]['endDate']['raw']] = ''
                dt = dict(reversed(list(dict(filter(lambda x:x[1], dic.items())).items())))
                data = {k:v for k, v in {(i * 1000):int(dt[i]) for i in dt}.items() if k > timestamp}
            else:
                dt = test
                data = {k:v for k, v in {(int(time.mktime(datetime.strptime(i, "%Y-%m-%d").timetuple())) * 1000):int(dt[i]) for i in dt}.items() if k > timestamp}
            return data

        def quarterly_real_equity():
            result = YahooData('balanceSheetHistoryQuarterly', 'balanceSheetStatements')
            timestamp = stock_data[2] - 9162400000
            class assets:
                dictt = MacroData('total-assets', 'Quarterly Total Assets')
                test = dict(filter(lambda x:x[1], dictt.items()))
                if len(test) == 0:
                    dic = {}
                    for i in range(len(result)):
                        try:
                            dic[result[i]['endDate']['fmt']] = str(result[i]['totalAssets']['raw'])[:-6]
                        except:
                            dic[result[i]['endDate']['fmt']] = ''
                    data = dict(list(dict(filter(lambda x:x[1], dic.items())).items()))
                else:
                    data = test

            class liabilities:
                dictt = MacroData('total-liabilities', 'Quarterly Total Liabilities')
                test = dict(filter(lambda x:x[1], dictt.items()))
                if len(test) == 0:
                    dic = {}
                    for i in range(len(result)):
                        try:
                            dic[result[i]['endDate']['fmt']] = str(result[i]['totalLiab']['raw'])[:-6]
                        except:
                            dic[result[i]['endDate']['fmt']] = ''
                    data = dict(list(dict(filter(lambda x:x[1], dic.items())).items()))
                else:
                    data = test

            real_equity = {}
            for t in range(len(liabilities.data)):
                d = list(assets.data)[t]
                f = int(assets.data[list(assets.data)[t]])
                g = int(liabilities.data[list(liabilities.data)[t]])
                real_equity[d] = int((f / 2) - g)
                t += 1
            dt = dict(reversed(list(real_equity.items())))
            data = {k:v for k, v in {(int(time.mktime(datetime.strptime(i, "%Y-%m-%d").timetuple())) * 1000):dt[i] for i in dt}.items() if k > timestamp}
            return data

        market_cap = stock_data[3]
        market_cap[1234] = -1000000

        def revenue(q):
          revenue = annual_revenue()
          revenue[list(revenue)[-1]+150000000000] = 1
          q.put_nowait(revenue)

        def income(q):
          income = annual_net_income()
          income[list(income)[-1]+150000000000] = 1
          q.put_nowait(income)

        def real_equity(q):
          real_equity = quarterly_real_equity()
          real_equity[list(real_equity)[-1]+150000000000] = 1
          q.put_nowait(real_equity)

        def equity(q):
          equity = quarterly_equity()
          equity[list(equity)[-1]+150000000000] = 1
          q.put_nowait(equity)

        qe = queue.Queue()
        qe2 = queue.Queue()
        qe3 = queue.Queue()
        qe4 = queue.Queue()
        qe5 = queue.Queue()
        t = threading.Thread(target=revenue, args=[qe])
        t2 = threading.Thread(target=income, args=[qe2])
        t3 = threading.Thread(target=real_equity, args=[qe3])
        t4 = threading.Thread(target=equity, args=[qe4])
        t5 = threading.Thread(target=Name, args=[qe5])
        t.start()
        t2.start()
        t3.start()
        t4.start()
        t5.start()

        revenue = qe.get()
        income = qe2.get()
        real_equity = qe3.get()
        equity = qe4.get()
        Name = qe5.get()

        ire = {}
        inc_key = 0
        r_e_key = 0
        e_key = 0
        r_key = 0
        lene = len(list(market_cap))
        for i in range(lene):
          inc = 0
          r_e = 0
          e = 0
          r = 0
          if income[list(income)[inc_key]] > 0:
            if list(market_cap)[i] < list(income)[inc_key+1]:
              inc = income[list(income)[inc_key]]
            else:
              inc = income[list(income)[inc_key+1]]
              inc_key += 1
            if list(market_cap)[i] < list(real_equity)[r_e_key+1]:
              r_e = real_equity[list(real_equity)[r_e_key]]
            else:
              r_e = real_equity[list(real_equity)[r_e_key+1]]
              r_e_key += 1
            if list(market_cap)[i] < list(equity)[e_key+1]:
              e = equity[list(equity)[e_key]]
            else:
              e = equity[list(equity)[e_key+1]]
              e_key += 1
            if list(market_cap)[i] < list(revenue)[r_key+1]:
              r = revenue[list(revenue)[r_key]]
            else:
              r = revenue[list(revenue)[r_key+1]]
              r_key += 1
          else:
            if list(market_cap)[i] < list(income)[inc_key+1]:
              inc = 0
              r_e = 0
              e = 0
              r = 0
            else:
              inc_key += 1
              r_key += 1
          ire[list(market_cap)[i]] = [inc, r_e, e, r]

        dt = {}
        mr_cap = [(int(market_cap[i]*1000)) for i in market_cap]

        mr_cap_list = list(market_cap)
        for i in range(lene):
            name = ''
            color = ''
            if mr_cap[i] == -1000000000:
                name = 'END'
                color = '#END'
            elif ire[list(ire)[i]][0] == 0:
                name = 'Loss Period'
                color = '#FFFFFF'
            else:
                rev = ire[list(ire)[i]][3]
                if rev > 1000:
                  min_payback_period = 20
                  max_payback_period = 30
                else:
                  min_payback_period = 10
                  max_payback_period = 20
                incom = ire[list(ire)[i]][0]
                minimal = incom*min_payback_period+ire[list(ire)[i]][1]
                maximal = incom*max_payback_period+ire[list(ire)[i]][2]
                if mr_cap[i] < maximal and mr_cap[i] > minimal:
                    name = 'Fair value'
                    color = '#FFB800'
                elif mr_cap[i] > maximal:
                    name = 'Overvalued'
                    color = '#FF1E1E'
                elif mr_cap[i] < minimal:
                    name = 'Undervalued'
                    color = '#00CC66'
            dt[mr_cap_list[i]] = [market_cap[mr_cap_list[i]], name, color]

        color = []
        final = []
        x = {}
        color.append(dt[list(dt)[0]][2])
        x['name'] = dt[list(dt)[0]][1]
        data = []
        for i in range(lene):
          if dt[list(dt)[i]][2] == color[-1]:
            data.append([list(dt)[i], dt[list(dt)[i]][0]])
          else:
            data.append([list(dt)[i], dt[list(dt)[i]][0]])
            copy = data.copy()
            x['data'] = copy
            x_copy = x.copy()
            final.append(x_copy)
            color.append(dt[list(dt)[i]][2])
            data.clear()
            x.clear()
            data.append([list(dt)[i], dt[list(dt)[i]][0]])
            x['name'] = dt[list(dt)[i]][1]
        final[-1][list(final[-1])[-1]].pop()
        market_cap.pop(list(market_cap)[-1])

        dat = [income[list(income)[-2]], real_equity[list(real_equity)[-2]], equity[list(equity)[-2]], revenue[list(revenue)[-2]]]
        def shown_data():
          currency = Ticker(tkr).summary_detail[tkr]['currency']
          def name(q):
            name =  Name
            link = Ticker(tkr).asset_profile[tkr]['website']
            data = [name, link]
            q.put_nowait(data)

          def markett_cap(q):
            mar_cap = float("%.2f"%(market_cap[list(market_cap)[-1]] * 10000000))
            dt = format_currency(str(mar_cap)[:1], currency, locale='en')[:-4]+numerize(int(str(mar_cap)[:3].ljust(len(str(mar_cap)), '0')), 2)
            data = dt[:-1]+' '+dt[-1]
            q.put_nowait(data)

          def price(q):
            price = stock_data[4][list(stock_data[4])[-1]]
            if price > 100:
                data = format_currency(str(price), currency, locale='en')[:-3]
            else:
                data = format_currency(str(price)[:1], currency, locale='en')[:-4]+str(price)[:4]
            q.put_nowait(data)

          def revenue(q):
            revenue = dat[3] * 1000000
            dt = format_currency(str(revenue)[:1], currency, locale='en')[:-4]+numerize(int(str(revenue)[:3].ljust(len(str(revenue)), '0')), 2)
            data = dt[:-1]+' '+dt[-1]
            q.put_nowait(data)

          def income(q):
            income = dat[0] * 1000000
            try:
                formated = format_currency(str(income)[:1], currency, locale='en')[:-4]
            except:
                formated = format_currency(str(income)[:2], currency, locale='en')[:-4]
            dt = formated+numerize(int(str(abs(income))[:3].ljust(len(str(abs(income))), '0')), 2)
            if income > 0:
                title = 'Net income'
            else:
                title = 'Net loss'
            data = [dt[:-1]+' '+dt[-1], title]
            q.put_nowait(data)

          def equity(q):
            equity = dat[2] * 1000000
            try:
                formated = format_currency(str(equity)[:1], currency, locale='en')[:-4]
            except:
                formated = format_currency(str(equity)[:2], currency, locale='en')[:-4]
            dt = formated+numerize(int(str(abs(equity))[:3].ljust(len(str(abs(equity))), '0')), 2)
            data = dt[:-1]+' '+dt[-1]
            q.put_nowait(data)

          def bankruptcy_equity(q):
            bankruptcy_equity = dat[1] * 1000000
            try:
                formated = format_currency(str(bankruptcy_equity)[:1], currency, locale='en')[:-4]
            except:
                formated = format_currency(str(bankruptcy_equity)[:2], currency, locale='en')[:-4]
            dt = formated+numerize(int(str(abs(bankruptcy_equity))[:3].ljust(len(str(abs(bankruptcy_equity))), '0')), 2)
            data = dt[:-1]+' '+dt[-1]
            q.put_nowait(data)

          def payback_time(q):
            try:
                payback_time = str(int(Ticker(tkr).summary_detail[tkr]['trailingPE']))+' years'
            except:
                payback_time = 'Undefined'
            q.put_nowait(payback_time)

          def dividends(q):
            try:
                dividends = str(Ticker(tkr).summary_detail[tkr]['fiveYearAvgDividendYield'])+'%'
            except:
                dividends = 'Don’t pay'
            q.put_nowait(dividends)

          def pendulum(q):
            mar_cap = market_cap[list(market_cap)[-1]] * 1000
            if dat[0] < 0:
              name = 'Loss period'
              color = '#FFFFFF'
              shown_percent = 'No'
              x = 0
              y = 0
              line_angle = 0
              ball = 'To calculate the fair value of the company, we need the annual net income, this company made a loss.'
              shown_minimal = 0
              shown_medium = 0
              shown_maximal = 0
            else:
              rev = dat[3]
              if rev > 1000:
                min_payback_period = 20
                max_payback_period = 30
              else:
                min_payback_period = 10
                max_payback_period = 20

              incom = dat[0]
              minimal = incom*min_payback_period+dat[1] 
              if minimal < 0:
                minimal = 0
              else:
                minimal = minimal
              maximal = incom*max_payback_period+dat[2]
              if maximal < 0:
                maximal = 0
              else:
                maximal = maximal
              medium = int((minimal+maximal)/2)
              if maximal > mar_cap and minimal < mar_cap:
                shown_percent = str(0)+'%'
              elif maximal == mar_cap or minimal == mar_cap:
                shown_percent = str(0)+'%'
              elif medium == 0:
                shown_percent = str(0)+'%'
              elif mar_cap < minimal:
                shown_percent = str(numerize(int((minimal-mar_cap)/mar_cap*100), 1))+'%'
              else:
                  shown_percent = str(numerize(int((mar_cap-maximal)/maximal*100), 1))+'%'

              if mar_cap < maximal and mar_cap > minimal:
                  name = 'Fair value'
                  color = '#FFB800'
              elif mar_cap > maximal:
                  name = 'Overvalued'
                  color = '#FF1E1E'
              elif mar_cap < minimal:
                  name = 'Undervalued'
                  color = '#00CC66'
              elif mar_cap == maximal or mar_cap == minimal:
                  name = 'Fair value'
                  color = '#FFB800'

              ball = numerize(int(str(mar_cap * 10000)[:3].ljust(len(str(mar_cap * 10000)), '0')), 2)[:-1]
              if minimal < 1000:
                shown_minimal = minimal
              else:
                shown_minimal = numerize(int(str(minimal)[:3].ljust(len(str(minimal)), '0')), 2)[:-1]
              if medium < 1000:
                shown_medium = medium
              else:
                shown_medium = numerize(int(str(medium)[:3].ljust(len(str(medium)), '0')), 2)[:-1]
              if maximal < 1000:
                shown_maximal = maximal
              else:
                shown_maximal = numerize(int(str(maximal)[:3].ljust(len(str(maximal)), '0')), 2)[:-1]
              
              if medium == 0 and market_cap == 0 or medium == market_cap and maximal == minimal:
                x_formula = 0
              else:
                x_formula = (mar_cap-medium)/((maximal-medium)*0.02)*0.37
              if x_formula > 37:
                  x = 37
              elif x_formula < -37:
                  x = -37
              else:
                  x = x_formula
              y = sqrt(47.6**2-(x*0.91214374783)**2)
              line_angle = arctan((-x-0)/(y * 1.10316040549-0)) * 180/pi
            data = [name, color, shown_percent, x, y, line_angle, ball, shown_minimal, shown_medium, shown_maximal]
            q.put_nowait(data)

          se = queue.Queue()
          se1 = queue.Queue()
          se2 = queue.Queue()
          se3 = queue.Queue()
          se4 = queue.Queue()
          se5 = queue.Queue()
          se6 = queue.Queue()
          se7 = queue.Queue()
          se8 = queue.Queue()
          se9 = queue.Queue()
          s = threading.Thread(target=name, args=[se])
          s1 = threading.Thread(target=markett_cap, args=[se1])
          s2 = threading.Thread(target=price, args=[se2])
          s3 = threading.Thread(target=revenue, args=[se3])
          s4 = threading.Thread(target=income, args=[se4])
          s5 = threading.Thread(target=equity, args=[se5])
          s6 = threading.Thread(target=bankruptcy_equity, args=[se6])
          s7 = threading.Thread(target=payback_time, args=[se7])
          s8 = threading.Thread(target=dividends, args=[se8])
          s9 = threading.Thread(target=pendulum, args=[se9])
          s.start()
          s1.start()
          s2.start()
          s3.start()
          s4.start()
          s5.start()
          s6.start()
          s7.start()
          s8.start()
          s9.start()
          ge = se.get()
          ge1 = se1.get()
          ge2 = se2.get()
          ge3 = se3.get()
          ge4 = se4.get()
          ge5 = se5.get()
          ge6 = se6.get()
          ge7 = se7.get()
          ge8 = se8.get()
          ge9 = se9.get()
          return [ge, ge1, ge2, ge3, ge4, ge5, ge6, ge7, ge8, ge9]

        main_data = shown_data()

        # get data for main screen
        title = main_data[0][0]
        link = main_data[0][1]
        m_cap = main_data[1]
        price = main_data[2]
        rev = main_data[3]
        inc_title = main_data[4][1]
        inco = main_data[4][0]
        equit = main_data[5]
        r_equit = main_data[6]
        payback = main_data[7]
        dividends = main_data[8]
        value = main_data[9][0]
        main_color = main_data[9][1]
        interest = main_data[9][2]
        left = main_data[9][3]
        top = main_data[9][4]
        rotate = main_data[9][5]
        ball = main_data[9][6]
        min_value = main_data[9][7]
        average_value = main_data[9][8]
        max_value = main_data[9][9]
        # get data for chart
        start_date = str(datetime.fromtimestamp(list(market_cap)[0] // 1000))
        oneM_date = str(datetime.fromtimestamp(list(market_cap)[-1] // 1000) - timedelta(1*365/12))
        oneY_date = str(datetime.fromtimestamp(list(market_cap)[-1] // 1000) - timedelta(12*365/12))
        all_date = str(datetime.fromtimestamp(list(market_cap)[-1] // 1000) - (datetime.fromtimestamp(list(market_cap)[-1] // 1000) - datetime.fromtimestamp(list(market_cap)[0] // 1000)))
        last_date = str(datetime.fromtimestamp(list(market_cap)[-1] // 1000))
        data = {
            # data for main screen
            'title': title,
            'link': link,
            'market_cap': m_cap,
            'price': price,
            'revenue': rev,
            'income_title': inc_title,
            'income': inco,
            'equity': equit,
            'bancruptcy_equity': r_equit,
            'payback_time': payback,
            'dividends': dividends,
            'value': value,
            'json_value': json.dumps(str(value)),
            'main_color': main_color,
            'interest': interest,
            'left': left,
            'top': top,
            'rotate': rotate,
            'ball': ball,
            'min_value': min_value,
            'average_value': average_value,
            'max_value': max_value,
            # data for chart
            'final': json.dumps(list(final)),
            'color': json.dumps(list(color)),
            'start_date': json.dumps(str(start_date)),
            'last_date': json.dumps(str(last_date)),
            'one_month': json.dumps(str(oneM_date)),
            'one_year': json.dumps(str(oneY_date)),
            'all_time': json.dumps(str(all_date))
        }
        return render(request, 'main/main.html', data)
    except:
        return redirect('not-found')

def not_found(request):
  return render(request, 'main/not_found.html')