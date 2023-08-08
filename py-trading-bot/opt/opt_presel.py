from core import presel
from core.presel import name_to_ust_or_presel, PreselWQ

import vectorbtpro as vbt
from vectorbtpro.utils.config import Config
import numpy as np

from opt.opt_main import OptMain, log

'''
Script to optimize the underlying combination of patterns/signals used for a given preselection strategy

The optimization takes place on the actions from CAC40, DAX and Nasdaq
Parameters very good on some actions but very bad for others should not be selected

The optimization algorithm calculates one point, look for the points around it and select the best one
As it can obviously lead to local maximum, the starting point is selected in a random manner
'''

vbt.settings['caching']=Config(
    disable=True,
    disable_whitelist=True,
    disable_machinery=True,
    silence_warnings=False,
    register_lazily=True,
    ignore_args=[
        'jitted',
        'chunked'
    ],
    use_cached_accessors=True
)

class Opt(OptMain):
    def __init__(
            self,
            class_name: str,
            period: str,
            **kwargs):
        super().__init__(period,**kwargs)
        self.pr={}

        for ind in self.indexes:
            if class_name[6:8].lower()=="wq":
                nb=int(class_name[8:])
                self.pr[ind]=PreselWQ(period,nb=nb, symbol_index=ind)
            else:
                PR=getattr(presel,class_name)
                self.pr[ind]=PR(period, symbol_index=ind)

            #no run otherwise it will crash, as ust is not splited

    def calculate_eq_ret(self,pf):
        '''
        Calculate an equivalent score for a portfolio  
        
        Arguments
        ----------
           pf: vbt portfolio
        ''' 
        m_rb=pf.total_market_return
        m_rr=pf.get_total_return()
        
        if abs(m_rb)<0.1: #avoid division by zero
            p=(m_rr)/ 0.1*np.sign(m_rb)   
        else:
            p=(m_rr- m_rb )/ abs(m_rb)

        return 4*p*(p<0) + p*(p>0) #wrong direction for the return are penalyzed
    
    def calculate_pf_sub(self,d):
        pf_dic={}   
        self.defi_ent(d)
        self.defi_ex(d)
        self.macro_mode(d)

        for ind in self.indexes: #CAC, DAX, NASDAQ
            self.tested_arrs=[] #reset after each loop
            
            self.pr[ind].ust.entries=self.ents[ind]
            self.pr[ind].ust.exits=self.exs[ind]
            self.pr[ind].close=self.close_dic[ind][d]
            self.pr[ind].run(skip_underlying=True)
            pf_dic[ind]=vbt.Portfolio.from_signals(self.data_dic[ind][d],
                                          self.pr[ind].entries,
                                          self.pr[ind].exits,
                                          short_entries=self.pr[ind].entries_short,
                                          short_exits=self.pr[ind].exits_short,
                                          freq="1d",fees=self.fees,
                                          call_seq='auto',cash_sharing=True
                                          ) #stop_exit_price="close"
            
        return pf_dic
    
    def calculate_pf(
            self,
            best_arrs_cand,
            best_ret_cand,
            best_arrs_ret,
            dic: str="learn",
            verbose: bool=False,
            )-> (list, list):
        '''
        To calculate a portfolio from strategy arrays
        
        Arguments
        ----------
           best_arrs_cand: table containing the best candidate by the strategy array presently tested
           best_ret_cand: table containing the return of the best candidate by the strategy array presently tested
           best_arrs_ret: table containing the return of the best candidate by the strategy array of the whole loop
        '''
        if not self.check_tested_arrs():
            print("return tested _arrs")
            return best_arrs_cand, best_ret_cand
        
        #create the underlying strategy
        ret=0
        ret_arr=[]
        
        pf_dic=self.calculate_pf_sub(dic)

        for ind in self.indexes: #CAC, DAX, NASDAQ    
            ret_arr.append(self.calculate_eq_ret(pf_dic[ind]))
        ret=self.summarize_eq_ret(ret_arr)
        trades =len(pf_dic[ind].get_trades().records_arr)
        del pf_dic

        if (ret> best_arrs_ret and ret>best_ret_cand and trades>50) or dic=="test":
            return self.calc_arrs, ret

        return best_arrs_cand, best_ret_cand
     
           