# -*- coding: utf-8 -*-
"""
Created on Mon Dec  7 10:32:11 2020

@author: aless
"""
import numpy as np
from utils.DQN import DeepNetworkModel
from utils.DDPG import CriticNetwork, ActorNetwork
import os, sys, pdb
import pandas as pd
from tqdm import tqdm
from typing import Union, Optional
from utils.SimulateData import ReturnSampler, GARCHSampler
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from utils.MarketEnv import MarketEnv, RecurrentMarketEnv
from utils.MarketEnv import ReturnSpace, HoldingSpace, ActionSpace
from utils.SimulateData import create_lstm_tensor
from utils.Regressions import CalculateLaggedSharpeRatio, RunModels
import collections
from natsort import natsorted
import re
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, ScalarFormatter
from matplotlib import cm
from utils.format_tousands import format_tousands


# LOAD UTILS
def load_DQNmodel(p, data_dir, ckpt=False, ckpt_it=None, ckpt_folder=None):

    num_inp = 2  # TODO insert number of factors as parameter
    if not p["zero_action"]:
        actions = np.arange(-p["KLM"][0], p["KLM"][0] + 1, p["KLM"][1])
        actions = actions[actions != 0]
    else:
        actions = np.arange(-p["KLM"][0], p["KLM"][0] + 1, p["KLM"][1])
    num_actions = len(actions)

    model = DeepNetworkModel(
        p["seed_init"],
        num_inp,
        p["hidden_units"],
        num_actions,
        p["batch_norm_input"],
        p["batch_norm_hidden"],
        p["activation"],
        p["kernel_initializer"],
        modelname="TrainNet",
    )

    if ckpt:
        if not ckpt_folder == "ckpt_pt":
            model.load_weights(
                os.path.join(data_dir, "ckpt", "DQN_{}_it_weights".format(ckpt_it))
            )
        else:
            model.load_weights(
                os.path.join(
                    data_dir, "ckpt_pt", "DQN_{}_it_pretrained_weights".format(ckpt_it)
                )
            )
    else:
        model.load_weights(os.path.join(data_dir, "DQN_final_weights"))

    return model, actions


class TrainedQTable:
    def __init__(self, Q_space):
        # generate row index of the dataframe with every possible combination
        # of state space variables
        self.Q_space = Q_space

    def getQvalue(self, state):
        ret = state[0]
        holding = state[1]
        return self.Q_space.loc[
            (ret, holding),
        ]

    def argmaxQ(self, state):
        return self.getQvalue(state).idxmax()

    def getMaxQ(self, state):
        return self.getQvalue(state).max()

    def chooseAction(self, state, epsilon):
        random_action = self.rng.random()
        if random_action < epsilon:
            # pick one action at random for exploration purposes
            # dn = self.ActionSpace.sample()
            dn = self.rng.choice(self.ActionSpace.values)

        else:
            # pick the greedy action
            dn = self.argmaxQ(state)

        return dn

    def chooseGreedyAction(self, state):
        return self.argmaxQ(state)


def load_Actor_Critic(
    p, data_dir, ckpt=False, ckpt_it=None, ckpt_folder=None, DDPG_type="DDPG"
):
    num_states = 2
    num_actions = 1

    if ckpt:
        if not ckpt_folder == "ckpt_pt":
            if DDPG_type == "DDPG":
                # Q_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
                #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
                #                                p['output_init'], p['delayed_actions'],
                #                                modelname='Qmodel')
                p_model = ActorNetwork(
                    p["seed_init"],
                    num_states,
                    p["hidden_units_p"],
                    num_actions,
                    p["batch_norm_input"],
                    p["batch_norm_hidden"],
                    p["activation_p"],
                    p["kernel_initializer"],
                    p["output_init"],
                    modelname="pmodel",
                )
                # Q_model.load_weights(os.path.join(data_dir, 'ckpt','Q_model_{}_it_weights'.format(ckpt_it)))
                p_model.load_weights(
                    os.path.join(
                        data_dir, "ckpt", "p_model_{}_it_weights".format(ckpt_it)
                    )
                )
            elif DDPG_type == "TD3":
                # Q1_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
                #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
                #                                p['output_init'], p['delayed_actions'],
                #                                modelname='Q1model')
                # Q2_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
                #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
                #                                p['output_init'], p['delayed_actions'],
                #                                modelname='Q2model')
                p_model = ActorNetwork(
                    p["seed_init"],
                    num_states,
                    p["hidden_units_p"],
                    num_actions,
                    p["batch_norm_input"],
                    p["batch_norm_hidden"],
                    p["activation_p"],
                    p["kernel_initializer"],
                    p["output_init"],
                    modelname="pmodel",
                )
                # Q1_model.load_weights(os.path.join(data_dir, 'ckpt','Q1_model_{}_it_weights'.format(ckpt_it)))
                # Q2_model.load_weights(os.path.join(data_dir, 'ckpt','Q2_model_{}_it_weights'.format(ckpt_it)))
                p_model.load_weights(
                    os.path.join(
                        data_dir, "ckpt", "p_model_{}_it_weights".format(ckpt_it)
                    )
                )
        else:
            # Q_model.load_weights(os.path.join(data_dir, 'ckpt_pt','Q_model_{}_it_pretrained_weights'.format(ckpt_it)))
            p_model.load_weights(
                os.path.join(
                    data_dir,
                    "ckpt_pt",
                    "p_model_{}_it_pretrained_weights".format(ckpt_it),
                )
            )
    else:
        if DDPG_type == "DDPG":
            # Q_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
            #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
            #                                p['output_init'], p['delayed_actions'],
            #                                modelname='Qmodel')
            p_model = ActorNetwork(
                p["seed_init"],
                num_states,
                p["hidden_units_p"],
                num_actions,
                p["batch_norm_input"],
                p["batch_norm_hidden"],
                p["activation_p"],
                p["kernel_initializer"],
                p["output_init"],
                modelname="pmodel",
            )
            # Q_model.load_weights(os.path.join(data_dir, 'Q_model_final_weights'))
            p_model.load_weights(os.path.join(data_dir, "p_model_final_weights"))
        elif DDPG_type == "TD3":
            # Q1_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
            #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
            #                                p['output_init'], p['delayed_actions'],
            #                                modelname='Q1model')
            # Q2_model = CriticNetwork(p['seed_init'], num_states, p['hidden_units_Q'], num_actions,
            #                                p['batch_norm_input'], p['batch_norm_hidden'], p['activation'], p['kernel_initializer'],
            #                                p['output_init'], p['delayed_actions'],
            #                                modelname='Q2model')
            p_model = ActorNetwork(
                p["seed_init"],
                num_states,
                p["hidden_units_p"],
                num_actions,
                p["batch_norm_input"],
                p["batch_norm_hidden"],
                p["activation_p"],
                p["kernel_initializer"],
                p["output_init"],
                modelname="pmodel",
            )
            # Q1_model.load_weights(os.path.join(data_dir, 'Q1_model_final_weights'))
            # Q2_model.load_weights(os.path.join(data_dir, 'Q2_model_final_weights'))
            p_model.load_weights(os.path.join(data_dir, "p_model_final_weights"))

    return p_model
    # if DDPG_type == 'DDPG':
    #     return Q_model, p_model
    # elif DDPG_type == 'TD3':
    #     return Q1_model, Q2_model, p_model


# TEST UTILS
def Out_sample_Misspec_test(
    N_test: int,
    df: np.ndarray,
    factor_lb: list,
    Startholding: Union[float or int],
    CostMultiplier: float,
    kappa: float,
    discount_rate: float,
    executeDRL: bool,
    executeRL: bool,
    executeMV: bool,
    RT: list,
    KLM: list,
    executeGP: bool,
    TrainNet,
    iteration: int,
    recurrent_env: bool = False,
    unfolding: int = 1,
    QTable: Optional[pd.DataFrame] = None,
    action_limit=None,
    datatype: str = "real",
    mean_process: str = "Constant",
    lags_mean_process: Union[int or None] = None,
    vol_process: str = "GARCH",
    distr_noise: str = "normal",
    seed: int = None,
    seed_param: int = None,
    sigmaf: Union[float or list or np.ndarray] = None,
    f0: Union[float or list or np.ndarray] = None,
    f_param: Union[float or list or np.ndarray] = None,
    sigma: Union[float or list or np.ndarray] = None,
    HalfLife: Union[int or list or np.ndarray] = None,
    uncorrelated: bool = False,
    degrees: int = None,
    rng=None,
    variables: list = None,
    bandwidth: float = None,
    tag="DQN",
):

    if datatype == "real":
        y, X = df[df.columns[0]], df[df.columns[1:]]
        dates = df.index

    elif datatype == "garch":
        return_series, params = GARCHSampler(
            N_test + factor_lb[-1] + 2,
            mean_process=mean_process,
            lags_mean_process=lags_mean_process,
            vol_process=vol_process,
            distr_noise=distr_noise,
            seed=seed,
            seed_param=seed_param,
        )
        df = CalculateLaggedSharpeRatio(
            return_series, factor_lb, nameTag=datatype, seriestype="return"
        )
        y, X = df[df.columns[0]], df[df.columns[1:]]
        dates = df.index

    elif datatype == "t_stud":
        plot_inputs = False
        # df freedom for t stud distribution are hard coded inside the function
        returns, factors, test_f_speed = ReturnSampler(
            N_test + factor_lb[-1],
            sigmaf,
            f0,
            f_param,
            sigma,
            plot_inputs,
            HalfLife,
            rng=rng,
            offset=unfolding + 1,
            uncorrelated=uncorrelated,
            seed_test=seed,
            t_stud=True,
            degrees=degrees,
        )

        df = CalculateLaggedSharpeRatio(
            returns, factor_lb, nameTag=datatype, seriestype="return"
        )
        y, X = df[df.columns[0]], df[df.columns[1:]]
        dates = df.index

    elif datatype == "t_stud_mfit":
        plot_inputs = False
        # df freedom for t stud distribution are hard coded inside the function
        if factor_lb:
            returns, factors, test_f_speed = ReturnSampler(
                N_test + factor_lb[-1],
                sigmaf,
                f0,
                f_param,
                sigma,
                plot_inputs,
                HalfLife,
                rng=rng,
                offset=unfolding + 1,
                uncorrelated=uncorrelated,
                seed_test=seed,
                t_stud=True,
                degrees=degrees,
            )
            df = pd.DataFrame(
                data=np.concatenate([returns.reshape(-1, 1), factors], axis=1)
            ).loc[factor_lb[-1] :]
            y, X = df[df.columns[0]], df[df.columns[1:]]
        else:
            returns, factors, test_f_speed = ReturnSampler(
                N_test,
                sigmaf,
                f0,
                f_param,
                sigma,
                plot_inputs,
                HalfLife,
                rng=rng,
                offset=unfolding + 1,
                uncorrelated=uncorrelated,
                seed_test=seed,
                t_stud=True,
                degrees=degrees,
            )
            df = pd.DataFrame(
                data=np.concatenate([returns.reshape(-1, 1), factors], axis=1)
            )
            y, X = df[df.columns[0]], df[df.columns[1:]]
        dates = df.index

    elif datatype == "garch_mr":

        plot_inputs = False
        # df freedom for t stud distribution are hard coded inside the function

        returns, factors, f_speed = ReturnSampler(
            N_test + factor_lb[-1],
            sigmaf,
            f0,
            f_param,
            sigma,
            plot_inputs,
            HalfLife,
            rng=rng,
            offset=unfolding + 1,
            uncorrelated=uncorrelated,
            t_stud=False,
            vol = 'heterosk',
        )
        
        df = CalculateLaggedSharpeRatio(
            returns, factor_lb, nameTag=datatype, seriestype="return"
        )
        y, X = df[df.columns[0]], df[df.columns[1:]]
        dates = df.index


    else:
        print("Datatype not correct")
        sys.exit()

    if datatype == "t_stud_mfit":
        params_meanrev, _ = RunModels(y, X, mr_only=True)
    else:
        # do regressions
        params_retmodel, params_meanrev, _, _ = RunModels(y, X)
        # get results
    test_returns = df.iloc[:, 0].values
    test_factors = df.iloc[:, 1:].values

    if datatype != "t_stud_mfit":
        sigma_fit = df.iloc[:, 0].std()
        f_param_fit = params_retmodel["params"]
    else:
        sigma_fit = sigma
        f_param_fit = f_param
    test_f_speed_fit = np.abs(
        np.array([*params_meanrev.values()]).ravel()
    )  # TODO check if abs is correct
    HalfLife_fit = np.around(np.log(2) / test_f_speed_fit, 2)

    if recurrent_env:
        test_returns_tens = create_lstm_tensor(test_returns.reshape(-1, 1), unfolding)
        test_factors_tens = create_lstm_tensor(test_factors, unfolding)
        test_env = RecurrentMarketEnv(
            HalfLife_fit,
            Startholding,
            sigma_fit,
            CostMultiplier,
            kappa,
            N_test,
            discount_rate,
            f_param_fit,
            test_f_speed_fit,
            test_returns,
            test_factors,
            test_returns_tens,
            test_factors_tens,
            action_limit,
            dates=dates,
        )
    else:
        test_env = MarketEnv(
            HalfLife_fit,
            Startholding,
            sigma_fit,
            CostMultiplier,
            kappa,
            N_test,
            discount_rate,
            f_param_fit,
            test_f_speed_fit,
            test_returns,
            test_factors,
            action_limit,
            dates=dates,
        )
    if "DQN" in tag:
        action_space = ActionSpace(KLM, zero_action=True)
    if executeDRL:
        CurrState, _ = test_env.reset()
    if executeRL:
        test_env.returns_space = ReturnSpace(RT)
        test_env.holding_space = HoldingSpace(KLM)
        DiscrCurrState = test_env.discrete_reset()
    if executeGP:
        CurrOptState = test_env.opt_reset()
        OptRate, DiscFactorLoads = test_env.opt_trading_rate_disc_loads()
    if executeMV:
        CurrMVState = test_env.opt_reset()

    if datatype == "real":
        if recurrent_env:
            cycle_len = N_test - 1 - (unfolding - 1)
        else:
            cycle_len = N_test - 1
    elif datatype != "real":
        if recurrent_env:
            cycle_len = N_test + 1 - (unfolding - 1)
        else:
            cycle_len = N_test + 1

    for i in tqdm(iterable=range(cycle_len), desc="Testing DQNetwork"):
        if executeDRL:
            if "DQN" in tag:
                #                 shares_traded = TrainNet.greedy_action(CurrState)
                shares_traded = action_space.values[
                    np.argmax(
                        TrainNet(
                            np.atleast_2d(CurrState.astype("float32")), training=False
                        )[0]
                    )
                ]
                NextState, Result, NextFactors = test_env.step(
                    CurrState, shares_traded, i
                )
                test_env.store_results(Result, i)
            elif "DDPG" in tag:
                tg = "DDPG"
                shares_traded = TrainNet(
                    np.atleast_2d(CurrState.astype("float32")), training=False
                )
                NextState, Result, NextFactors = test_env.step(
                    CurrState, shares_traded, i, tag=tg
                )
                test_env.store_results(Result, i)
            CurrState = NextState

        if executeRL:
            shares_traded = int(QTable.chooseGreedyAction(DiscrCurrState))
            DiscrNextState, Result = test_env.discrete_step(
                DiscrCurrState, shares_traded, i
            )
            test_env.store_results(Result, i)
            DiscrCurrState = DiscrNextState

        if executeGP:
            NextOptState, OptResult = test_env.opt_step(
                CurrOptState, OptRate, DiscFactorLoads, i
            )
            test_env.store_results(OptResult, i)
            CurrOptState = NextOptState

        if executeMV:
            NextMVState, MVResult = test_env.mv_step(CurrMVState, i)
            test_env.store_results(MVResult, i)
            CurrMVState = NextMVState

    p_avg, r_avg, sr_avg, absp_avg, absr_avg, abssr_avg, abssr_hold = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for t in tag:
        # select interesting variables and express as a percentage of the GP results
        pnl_str = list(filter(lambda x: "NetPNL_{}".format(t) in x, variables))
        opt_pnl_str = list(filter(lambda x: "OptNetPNL" in x, variables))
        rew_str = list(filter(lambda x: "Reward_{}".format(t) in x, variables))
        opt_rew_str = list(filter(lambda x: "OptReward" in x, variables))

        # pnl

        pnl = test_env.res_df[pnl_str + opt_pnl_str].iloc[:-1]
        # if bandwidth:
        #     mean = pnl[pnl_str].mean()
        #     std = pnl[pnl_str].std()
        #     pnl.loc[pnl[pnl_str] <= mean - bandwidth*std,pnl_str] = mean - bandwidth*std
        #     pnl.loc[pnl[pnl_str] >= mean + bandwidth*std,pnl_str] = mean + bandwidth*std
        cum_pnl = pnl.cumsum()

        # if datatype == 'garch' or datatype == 't_stud':
        if datatype == "garch" or datatype=='garch_mr':
            ref_pnl = np.array(cum_pnl[pnl_str]) - np.array(cum_pnl[opt_pnl_str])
        else:
            ref_pnl = (
                np.array(cum_pnl[pnl_str]) / np.array(cum_pnl[opt_pnl_str])
            ) * 100

        # rewards
        rew = test_env.res_df[rew_str + opt_rew_str].iloc[:-1]
        # if bandwidth:
        #     mean = rew[rew_str].mean()
        #     std = rew[rew_str].std()
        #     rew.loc[rew[rew_str] <= mean - bandwidth*std,rew_str] = mean - bandwidth*std
        #     rew.loc[rew[rew_str] >= mean + bandwidth*std,rew_str] = mean + bandwidth*std
        cum_rew = rew.cumsum()
        # if datatype == 'garch' or datatype == 't_stud':
        if datatype == "garch" or datatype == "garch_mr":
            ref_rew = np.array(cum_rew[rew_str]) - np.array(cum_rew[opt_rew_str])
        else:
            ref_rew = (
                np.array(cum_rew[rew_str]) / np.array(cum_rew[opt_rew_str])
            ) * 100

        # SR
        # pnl = test_env.res_df[pnl_str+opt_pnl_str].iloc[:-1]
        mean = np.array(pnl[pnl_str]).mean()
        std = np.array(pnl[pnl_str]).std()
        sr = (mean / std) * (252 ** 0.5)

        # Holding
        hold = test_env.res_df["NextHolding_{}".format(t)].iloc[
            -2
        ]  # avoid last observation
        opthold = test_env.res_df["OptNextHolding"].iloc[-2]

        opt_mean = np.array(pnl[opt_pnl_str]).mean()
        opt_std = np.array(pnl[opt_pnl_str]).std()
        optsr = (opt_mean / opt_std) * (252 ** 0.5)

        perc_SR = (sr / optsr) * 100

        p_avg.append(ref_pnl[-1])
        r_avg.append(ref_rew[-1])
        sr_avg.append(perc_SR)

        absp_avg.append(cum_pnl.iloc[-1].values[0])
        absr_avg.append(cum_rew.iloc[-1].values[0])
        abssr_avg.append(sr)

        abssr_hold.append(hold)

    # return only the last value of the series which is the cumulated pnl expressed as a percentage of GP
    return (
        np.array(p_avg).ravel(),
        np.array(r_avg).ravel(),
        np.array(sr_avg).ravel(),
        np.array(absp_avg).ravel(),
        cum_pnl.iloc[-1].values[1],
        np.array(absr_avg).ravel(),
        cum_rew.iloc[-1].values[1],
        np.array(abssr_avg).ravel(),
        optsr,
        np.array(abssr_hold).ravel(),
        opthold,
    )


def Out_sample_test(
    N_test: int,
    sigmaf: Union[float or list or np.ndarray],
    f0: Union[float or list or np.ndarray],
    f_param: Union[float or list or np.ndarray],
    sigma: Union[float or list or np.ndarray],
    plot_inputs: int,
    HalfLife: Union[int or list or np.ndarray],
    Startholding: Union[float or int],
    CostMultiplier: float,
    kappa: float,
    discount_rate: float,
    executeDRL: bool,
    executeRL: bool,
    executeMV: bool,
    RT: list,
    KLM: list,
    executeGP: bool,
    TrainNet,
    iteration: int,
    recurrent_env: bool = False,
    unfolding: int = 1,
    QTable: Optional[pd.DataFrame] = None,
    rng: int = None,
    seed_test: int = None,
    action_limit=None,
    uncorrelated=False,
    t_stud: bool = False,
    variables: list = None,
    bandwidth: float = None,
    tag="DQN",
):

    test_returns, test_factors, test_f_speed = ReturnSampler(
        N_test,
        sigmaf,
        f0,
        f_param,
        sigma,
        plot_inputs,
        HalfLife,
        rng,
        offset=unfolding + 1,
        seed_test=seed_test,
        uncorrelated=uncorrelated,
        t_stud=t_stud,
    )

    if recurrent_env:
        test_returns_tens = create_lstm_tensor(test_returns.reshape(-1, 1), unfolding)
        test_factors_tens = create_lstm_tensor(test_factors, unfolding)
        test_env = RecurrentMarketEnv(
            HalfLife,
            Startholding,
            sigma,
            CostMultiplier,
            kappa,
            N_test,
            discount_rate,
            f_param,
            test_f_speed,
            test_returns,
            test_factors,
            test_returns_tens,
            test_factors_tens,
            action_limit,
        )
    else:
        test_env = MarketEnv(
            HalfLife,
            Startholding,
            sigma,
            CostMultiplier,
            kappa,
            N_test,
            discount_rate,
            f_param,
            test_f_speed,
            test_returns,
            test_factors,
            action_limit,
        )
    if "DQN" in tag:
        action_space = ActionSpace(KLM, zero_action=True)
    if executeDRL:
        CurrState, _ = test_env.reset()
    if executeRL:
        test_env.returns_space = ReturnSpace(RT)
        test_env.holding_space = HoldingSpace(KLM)
        DiscrCurrState = test_env.discrete_reset()
    if executeGP:
        CurrOptState = test_env.opt_reset()
        OptRate, DiscFactorLoads = test_env.opt_trading_rate_disc_loads()
    if executeMV:
        CurrMVState = test_env.opt_reset()

    for i in tqdm(iterable=range(N_test + 1), desc="Testing DQNetwork"):
        if executeDRL:
            if "DQN" in tag:
                #                 shares_traded = TrainNet.greedy_action(CurrState)
                shares_traded = action_space.values[
                    np.argmax(
                        TrainNet(
                            np.atleast_2d(CurrState.astype("float32")), training=False
                        )[0]
                    )
                ]
                NextState, Result, NextFactors = test_env.step(
                    CurrState, shares_traded, i
                )
                test_env.store_results(Result, i)
            elif "DDPG" in tag:
                tg = "DDPG"
                shares_traded = TrainNet(
                    np.atleast_2d(CurrState.astype("float32")), training=False
                )
                NextState, Result, NextFactors = test_env.step(
                    CurrState, shares_traded, i, tag=tg
                )
                test_env.store_results(Result, i)
            CurrState = NextState

        if executeRL:
            shares_traded = int(QTable.chooseGreedyAction(DiscrCurrState))
            DiscrNextState, Result = test_env.discrete_step(
                DiscrCurrState, shares_traded, i
            )
            test_env.store_results(Result, i)
            DiscrCurrState = DiscrNextState

        if executeGP:
            NextOptState, OptResult = test_env.opt_step(
                CurrOptState, OptRate, DiscFactorLoads, i
            )
            test_env.store_results(OptResult, i)
            CurrOptState = NextOptState

        if executeMV:
            NextMVState, MVResult = test_env.mv_step(CurrMVState, i)
            test_env.store_results(MVResult, i)
            CurrMVState = NextMVState

    p_avg, r_avg, sr_avg, absp_avg, absr_avg, abssr_avg, abssr_hold = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    for t in tag:
        # select interesting variables and express as a percentage of the GP results
        pnl_str = list(filter(lambda x: "NetPNL_{}".format(t) in x, variables))
        opt_pnl_str = list(filter(lambda x: "OptNetPNL" in x, variables))
        rew_str = list(filter(lambda x: "Reward_{}".format(t) in x, variables))
        opt_rew_str = list(filter(lambda x: "OptReward" in x, variables))

        # pnl
        pnl = test_env.res_df[pnl_str + opt_pnl_str].iloc[:-1]
        # if bandwidth:
        #     mean = pnl[pnl_str].mean()
        #     std = pnl[pnl_str].std()
        #     pnl.loc[pnl[pnl_str] <= mean - bandwidth*std,pnl_str] = mean - bandwidth*std
        #     pnl.loc[pnl[pnl_str] >= mean + bandwidth*std,pnl_str] = mean + bandwidth*std
        cum_pnl = pnl.cumsum()
        ref_pnl = (np.array(cum_pnl[pnl_str]) / np.array(cum_pnl[opt_pnl_str])) * 100
        # rewards
        rew = test_env.res_df[rew_str + opt_rew_str].iloc[:-1]
        # if bandwidth:
        #     mean = rew[rew_str].mean()
        #     std = rew[rew_str].std()
        #     rew.loc[rew[rew_str] <= mean - bandwidth*std,rew_str] = mean - bandwidth*std
        #     rew.loc[rew[rew_str] >= mean + bandwidth*std,rew_str] = mean + bandwidth*std
        cum_rew = rew.cumsum()
        ref_rew = (np.array(cum_rew[rew_str]) / np.array(cum_rew[opt_rew_str])) * 100

        # SR
        # pnl = test_env.res_df[pnl_str+opt_pnl_str].iloc[:-1]
        mean = np.array(pnl[pnl_str]).mean()
        std = np.array(pnl[pnl_str]).std()
        sr = (mean / std) * (252 ** 0.5)

        # Holding
        hold = test_env.res_df["NextHolding_{}".format(t)].iloc[
            -2
        ]  # avoid last observation
        opthold = test_env.res_df["OptNextHolding"].iloc[-2]

        opt_mean = np.array(pnl[opt_pnl_str]).mean()
        opt_std = np.array(pnl[opt_pnl_str]).std()
        optsr = (opt_mean / opt_std) * (252 ** 0.5)

        perc_SR = (sr / optsr) * 100

        p_avg.append(ref_pnl[-1])
        r_avg.append(ref_rew[-1])
        sr_avg.append(perc_SR)

        absp_avg.append(cum_pnl.iloc[-1].values[0])
        absr_avg.append(cum_rew.iloc[-1].values[0])
        abssr_avg.append(sr)

        abssr_hold.append(hold)

    # return only the last value of the series which is the cumulated pnl expressed as a percentage of GP
    return (
        np.array(p_avg).ravel(),
        np.array(r_avg).ravel(),
        np.array(sr_avg).ravel(),
        np.array(absp_avg).ravel(),
        cum_pnl.iloc[-1].values[1],
        np.array(absr_avg).ravel(),
        cum_rew.iloc[-1].values[1],
        np.array(abssr_avg).ravel(),
        optsr,
        np.array(abssr_hold).ravel(),
        opthold,
    )


# PLOT UTILS
def prime_factors(n):
    i = 2
    factors = []
    while i * i <= n:
        if n % i:
            i += 1
        else:
            n //= i
            factors.append(i)
    if n > 1:
        factors.append(n)
    return factors


def get_figsize(columnwidth=243.91125, wf=0.5, hf=(5.0 ** 0.5 - 1.0) / 2.0):
    """Parameters:
      - wf [float]:  width fraction in columnwidth units
      - hf [float]:  height fraction in columnwidth units.
                      Set by default to golden ratio.
      - columnwidth [float]: width of the column in latex. Get this from LaTeX
                              using \showthe\columnwidth
    Returns:  [fig_width,fig_height]: that should be given to matplotlib
    """
    fig_width_pt = columnwidth * wf
    inches_per_pt = 1.0 / 72.27  # Convert pt to inch
    fig_width = fig_width_pt * inches_per_pt  # width in inches
    fig_height = fig_width * hf  # height in inches
    return (fig_width, fig_height)


def set_size(width, fraction=1, subplots=(1, 1)):
    """Set figure dimensions to avoid scaling in LaTeX.

    Parameters
    ----------
    width: float
            Document textwidth or columnwidth in pts
    fraction: float, optional
            Fraction of the width which you wish the figure to occupy

    Returns
    -------
    fig_dim: tuple
            Dimensions of figure in inches
    """
    # Width of figure (in pts)
    fig_width_pt = width * fraction

    # Convert from pt to inches
    inches_per_pt = 1 / 72.27

    # Golden ratio to set aesthetic figure height
    # https://disq.us/p/2940ij3
    golden_ratio = (5 ** 0.5 - 1) / 2

    # Figure width in inches
    fig_width_in = fig_width_pt * inches_per_pt
    # Figure height in inches
    # fig_height_in = fig_width_in * golden_ratio
    fig_height_in = fig_width_in * golden_ratio * (subplots[0] / subplots[1])

    fig_dim = (fig_width_in, fig_height_in)

    return fig_dim


def plot_multitest_OOS(
    df,
    data_dir,
    N_test,
    variable,
    colors=["b", "darkblue"],
    conf_interval=False,
    diff_colors=False,
):

    df_mean = df.mean(axis=0)

    fig = plt.figure(figsize=get_figsize(columnwidth=397.48499, wf=2.5, hf=0.7))
    # fig.subplots_adjust(wspace=0.2, hspace=0.6)
    ax1 = fig.add_subplot()

    idxs = [int(i) for i in df.iloc[0, :].index]
    # https://matplotlib.org/examples/color/colormaps_reference.html
    colormap = cm.get_cmap("plasma", len(df.index))
    for j, i in enumerate(df.index):
        if diff_colors:
            ax1.scatter(
                x=idxs,
                y=df.iloc[i, :],
                alpha=0.8,
                color=colormap.colors[j],
                marker="o",
                s=7.5,
            )
        else:
            ax1.scatter(
                x=idxs, y=df.iloc[i, :], alpha=0.6, color=colors[0], marker="o", s=7.5
            )

    ax1.plot(
        idxs,
        df_mean.values,
        color=colors[1],
        linewidth=3,
        label="Avg {} {}".format("DQN", variable.split("_")[0]),
    )
    if conf_interval:
        ci = 2 * np.std(df_mean.values)
        ax1.fill_between(
            idxs, (df_mean.values - ci), (df_mean.values + ci), color="b", alpha=0.1
        )
    # add benchmark series to plot the hline
    df.loc["Benchmark"] = 100.0
    ax1.plot(
        idxs,
        df.loc["Benchmark"].values,
        linestyle="--",
        linewidth=4,
        color="red",
        label="GP {}".format(variable.split("_")[0]),
    )

    ax1.set_title("{}".format(data_dir.split("/")[-2]))
    ax1.set_ylabel("% Reference {}".format(variable.split("_")[0]))
    ax1.set_xlabel("in-sample training iterations")
    # ax1.set_ylim(0,150)
    # ax1.legend()
    # scientific_formatter = FuncFormatter(scientific)
    ax1.xaxis.set_major_formatter(ScalarFormatter())
    ax1.yaxis.set_major_formatter(ScalarFormatter())
    fig.savefig(os.path.join(data_dir, "{}.pdf".format(variable)), dpi=300)


def plot_multitest_overlap_OOS(
    ax1,
    df,
    data_dir,
    N_test,
    variable,
    colors=["b", "darkblue"],
    conf_interval=False,
    diff_colors=False,
    params=None,
    plot_lr=False,
    plot_experience=False,
    plot_buffer=False,
):

    df_mean = df.mean(axis=0)

    idxs = [int(i) for i in df.iloc[0, :].index]
    # https://matplotlib.org/examples/color/colormaps_reference.html
    colormap = cm.get_cmap("plasma", len(df.index))
    for j, i in enumerate(df.index):
        if diff_colors:
            ax1.scatter(
                x=idxs,
                y=df.iloc[i, :],
                alpha=0.6,
                color=colormap.colors[j],
                marker="o",
                s=7.5,
            )
        else:
            ax1.scatter(
                x=idxs, y=df.iloc[i, :], alpha=0.6, color=colors, marker="o", s=7.5
            )

    pgarch = np.round(
        np.array(
            [
                [
                    value
                    for key, value in params.items()
                    if "garch_omega" in key.lower()
                ],
                [
                    value
                    for key, value in params.items()
                    if "garch_alpha" in key.lower()
                ],
                [value for key, value in params.items() if "garch_beta" in key.lower()],
            ]
        ).ravel(),
        2,
    )
    # if pgarch.size!=0:
    #     lab  = 'sp_{}_om_{}_alpha_{},beta_{}_sum_{}'.format(params['seedparam'],pgarch[0],pgarch[1],pgarch[2],np.round(sum(pgarch[1:]),2))
    #     ax1.plot(idxs,df_mean.values,color=colors,linewidth=3, label='Avg {} {} {}'.format('DQN',variable.split('_')[0],
    #                                                                                           lab))

    # else:
    ax1.plot(
        idxs,
        df_mean.values,
        color=colors,
        linewidth=3,
        label="Avg {} {} {}".format(
            "DQN", variable.split("_")[0], data_dir.split("/")[-2]
        ),
    )

    if conf_interval:
        ci = 2 * np.std(df_mean.values)
        ax1.fill_between(
            idxs, (df_mean.values - ci), (df_mean.values + ci), color=colors, alpha=0.5
        )
    # add benchmark series to plot the hline

    if 'datatype' not in params.keys():
        params['datatype'] = 'gp'
    if pgarch.size == 0 and 'garch' not in params['datatype']:
        df.loc["Benchmark"] = 100.0
        ax1.plot(
            idxs, df.loc["Benchmark"].values, linestyle="--", linewidth=4, color="red"
        )
        # ax1.set_ylim(-10000,300)
        ax1.set_ylim(0, 150)
        # ax1.set_ylim(-150,150)

    else:
        if variable.split("_")[0] != "SR":
            df.loc["Benchmark"] = 0.0
            ax1.plot(
                idxs,
                df.loc["Benchmark"].values,
                linestyle="--",
                linewidth=4,
                color="red",
            )
            if params["datatype"] == "t_stud":
                ax1.set_ylim(-1500000, 1500000)
                # ax1.set_ylim(0.0,1.0)
            elif params["datatype"] == "garch":
                # ax1.set_ylim(-100000,100000)
                ax1.set_ylim(-1000000, 1000000)
            elif params["datatype"] == "garch_mr":
                # ax1.set_ylim(-100000,100000)
                ax1.set_ylim(-5000000, 5000000)


        else:
            df.loc["Benchmark"] = 100.0
            ax1.plot(
                idxs,
                df.loc["Benchmark"].values,
                linestyle="--",
                linewidth=4,
                color="red",
            )
            ax1.set_ylim(0, 150)
            # ax1.set_ylim(-500,500)

    ax1.set_title("{}".format(data_dir.split("/")[-2]))
    ax1.set_ylabel("% Reference {}".format(variable.split("_")[0]))
    ax1.set_xlabel("in-sample training iterations")

    ax1.legend()
    # scientific_formatter = FuncFormatter(scientific)
    ax1.xaxis.set_major_formatter(ScalarFormatter())
    ax1.yaxis.set_major_formatter(ScalarFormatter())

    if plot_lr:
        N = idxs[-1]
        rates = pd.DataFrame()
        initial_learning_rate = params["learning_rate"]
        decay_rate = params["exp_decay_rate"]
        decay_steps = params["exp_decay_pct"] * N
        l = lr_exp_decay(N, initial_learning_rate, decay_rate, decay_steps)
        rates[decay_steps / N] = l

        rates = rates / initial_learning_rate * 100
        idxs[-1] = idxs[-1] - 1

        if "exp_decay_pct" in data_dir or "exp_decay_rate" in data_dir:
            ax1.plot(
                idxs, rates.iloc[idxs], lw=2, linestyle="-", color=colors, alpha=0.8
            )
        else:
            ax1.plot(
                idxs, rates.iloc[idxs], lw=2, linestyle="-", color="blue", alpha=0.8
            )  # , label='lr_{}'.format(data_dir.split('/')[-2]))#

    if plot_experience:
        N = idxs[-1]
        epsilon = 1.0
        min_eps_pct = params["min_eps_pct"]
        min_eps = params["min_eps"]
        steps_to_min_eps = int(N * min_eps_pct)
        eps_decay = (epsilon - min_eps) / steps_to_min_eps
        e = eps(N, epsilon, eps_decay, min_eps)
        e = e / epsilon * 100
        idxs[-1] = idxs[-1] - 1

        if "min_eps_pct" in data_dir:
            ax1.plot(idxs, e[idxs], lw=2, linestyle="--", color=colors, alpha=0.8)
        else:
            ax1.plot(idxs, e[idxs], lw=2, linestyle="--", color="blue", alpha=0.8)

    if plot_buffer:
        N = idxs[-1]
        max_exp_pct = params["max_exp_pct"]

        if "max_exp_pct" in data_dir:
            ax1.axvline(
                x=max_exp_pct * N, lw=2, linestyle="-.", color=colors, alpha=0.8
            )
        else:
            ax1.axvline(
                x=max_exp_pct * N, lw=2, linestyle="-.", color="blue", alpha=0.8
            )

    # fig.savefig(os.path.join(data_dir,'{}.pdf'.format(variable)), dpi=300)


def lr_exp_decay(N, initial_learning_rate, decay_rate, decay_steps):

    lrs = []

    for i in range(N):
        lr = initial_learning_rate * decay_rate ** (i / decay_steps)
        lrs.append(lr)

    return np.array(lrs)


def eps(N, epsilon, eps_decay, min_eps):

    eps = []

    for i in range(N):
        epsilon = max(min_eps, epsilon - eps_decay)
        eps.append(epsilon)

    return np.array(eps)


def plot_abs_pnl_OOS(
    ax1, df, data_dir, N_test, variable, colors=["b", "darkblue"], params=None
):

    df_mean = df.mean(axis=0)
    
    
    idxs = [int(i) for i in df.iloc[0, :].index]

    for j, i in enumerate(df.index):
        ax1.scatter(x=idxs, y=df.iloc[i, :], alpha=0.6, color=colors, marker="o", s=7.5)
    ax1.plot(
        idxs,
        df_mean.values,
        color=colors,
        linewidth=3,
        label="{} {} {}".format(
            variable.split("_")[0], variable.split("_")[3], data_dir.split("/")[-2]
        ),
    )

    ax1.set_title("{}".format(data_dir.split("/")[-2]))
    ax1.set_ylabel("{}".format(variable.split("_")[0]))
    ax1.set_xlabel("in-sample training iterations")

    ax1.legend()
    # scientific_formatter = FuncFormatter(scientific)
    ax1.xaxis.set_major_formatter(ScalarFormatter())
    ax1.yaxis.set_major_formatter(ScalarFormatter())
    ax1.set_ylim(-20000000, 20000000)


def plot_multitest_real_OOS(
    ax1,
    df,
    data_dir,
    N_test,
    variable,
    colors=["b", "darkblue"],
    conf_interval=False,
    diff_colors=False,
    params=None,
    plot_lr=False,
    plot_experience=False,
    plot_buffer=False,
):

    df_mean = df.mean(axis=0)
    # pdb.set_trace()
    if params['training'] == 'offline':
        idxs = [int(i)* params['len_series'] for i in df.iloc[0, :].index]
    else:
        idxs = [int(i) for i in df.iloc[0, :].index]
        
    # https://matplotlib.org/examples/color/colormaps_reference.html
    colormap = cm.get_cmap("plasma", len(df.index))
    for j, i in enumerate(df.index):
        if diff_colors:
            ax1.scatter(
                x=idxs,
                y=df.iloc[i, :],
                alpha=0.6,
                color=colormap.colors[j],
                marker="o",
                s=7.5,
            )
        else:
            ax1.scatter(
                x=idxs, y=df.iloc[i, :], alpha=0.6, color=colors, marker="o", s=7.5
            )



    ax1.plot(
        idxs,
        df_mean.values,
        color=colors,
        linewidth=3,
        label="Avg {} {} {}".format(
            "DQN", variable.split("_")[0], data_dir.split("/")[-2]
        ),
    )

    if conf_interval:
        ci = 2 * np.std(df_mean.values)
        ax1.fill_between(
            idxs, (df_mean.values - ci), (df_mean.values + ci), color=colors, alpha=0.5
        )
    # add benchmark series to plot the hline


    if variable.split("_")[0] != "SR":
        df.loc["Benchmark"] = 0.0
        ax1.plot(
            idxs,
            df.loc["Benchmark"].values,
            linestyle="--",
            linewidth=4,
            color="red",
        )

        ax1.set_ylim(-10000, 10000)

    else:
        df.loc["Benchmark"] = 100.0
        ax1.plot(
            idxs,
            df.loc["Benchmark"].values,
            linestyle="--",
            linewidth=4,
            color="red",
        )
        ax1.set_ylim(0, 150)


    ax1.set_title("{}".format(data_dir.split("/")[-2]))
    ax1.set_ylabel("% Reference {}".format(variable.split("_")[0]))
    ax1.set_xlabel("in-sample training iterations")

    ax1.legend()
    # scientific_formatter = FuncFormatter(scientific)
    ax1.xaxis.set_major_formatter(ScalarFormatter())
    ax1.yaxis.set_major_formatter(ScalarFormatter())

    if plot_lr:
        N = idxs[-1]
        rates = pd.DataFrame()
        initial_learning_rate = params["learning_rate"]
        decay_rate = params["exp_decay_rate"]
        decay_steps = params["exp_decay_pct"] * N
        l = lr_exp_decay(N, initial_learning_rate, decay_rate, decay_steps)
        rates[decay_steps / N] = l

        rates = rates / initial_learning_rate * 100
        idxs[-1] = idxs[-1] - 1

        if "exp_decay_pct" in data_dir or "exp_decay_rate" in data_dir:
            ax1.plot(
                idxs, rates.iloc[idxs], lw=2, linestyle="-", color=colors, alpha=0.8
            )
        else:
            ax1.plot(
                idxs, rates.iloc[idxs], lw=2, linestyle="-", color="blue", alpha=0.8
            )  # , label='lr_{}'.format(data_dir.split('/')[-2]))#

    if plot_experience:
        N = idxs[-1]
        epsilon = 1.0
        min_eps_pct = params["min_eps_pct"]
        min_eps = params["min_eps"]
        steps_to_min_eps = int(N * min_eps_pct)
        eps_decay = (epsilon - min_eps) / steps_to_min_eps
        e = eps(N, epsilon, eps_decay, min_eps)
        e = e / epsilon * 100
        idxs[-1] = idxs[-1] - 1

        if "min_eps_pct" in data_dir:
            ax1.plot(idxs, e[idxs], lw=2, linestyle="--", color=colors, alpha=0.8)
        else:
            ax1.plot(idxs, e[idxs], lw=2, linestyle="--", color="blue", alpha=0.8)

    if plot_buffer:
        N = idxs[-1]
        max_exp_pct = params["max_exp_pct"]

        if "max_exp_pct" in data_dir:
            ax1.axvline(
                x=max_exp_pct * N, lw=2, linestyle="-.", color=colors, alpha=0.8
            )
        else:
            ax1.axvline(
                x=max_exp_pct * N, lw=2, linestyle="-.", color="blue", alpha=0.8
            )

    # fig.savefig(os.path.join(data_dir,'{}.pdf'.format(variable)), dpi=300)

# def scientific(x, pos):
#     # x:  tick value - ie. what you currently see in yticks
#     # pos: a position - ie. the index of the tick (from 0 to 9 in this example)
#     return '%.2E' % x

########################################################################################################################
# Plot picture for the paper
def plot_multitest_paper(
    ax1,
    tag,
    df,
    data_dir,
    N_test,
    variable,
    colors=["b", "darkblue"],
    params=None,
    plt_bench=False,
):

    df_mean = df.mean(axis=0)

    idxs = [int(i) for i in df.iloc[0, :].index]
    for j, i in enumerate(df.index):
        ax1.scatter(
            x=idxs, y=df.iloc[i, :], alpha=0.15, color=colors, marker="o", s=0.5
        )

    pgarch = np.round(
        np.array(
            [
                [
                    value
                    for key, value in params.items()
                    if "garch_omega" in key.lower()
                ],
                [
                    value
                    for key, value in params.items()
                    if "garch_alpha" in key.lower()
                ],
                [value for key, value in params.items() if "garch_beta" in key.lower()],
            ]
        ).ravel(),
        2,
    )

    ax1.plot(idxs, df_mean.values, color=colors, linewidth=1.0, label=tag)

    # if 'datatype' in params:
    #     cond = params['datatype']!='t_stud'
    # else:
    #     cond = True
    cond = True
    # if pgarch.size==0 and params['datatype']!='t_stud':

    if plt_bench:
        if pgarch.size == 0 and cond:
            df.loc["Benchmark"] = 100.0
            ax1.plot(
                idxs,
                df.loc["Benchmark"].values,
                linestyle="--",
                linewidth=1.5,
                color="red",
                label="benchmark",
            )

            ax1.set_ylim(20, 130)
            # ax1.set_ylim(20,120)

        else:
            if variable.split("_")[0] != "SR":
                df.loc["Benchmark"] = 0.0
                ax1.plot(
                    idxs,
                    df.loc["Benchmark"].values,
                    linestyle="--",
                    linewidth=1.5,
                    color="red",
                )
                if params["datatype"] == "t_stud":
                    ax1.set_ylim(-1500000, 1500000)
                    # ax1.set_ylim(0.0,1.0)
                elif params["datatype"] == "garch":
                    # ax1.set_ylim(-100000,100000)

                    ax1.set_ylim(-1000000, 1000000)
                    # pass

            else:
                df.loc["Benchmark"] = 100.0
                ax1.plot(
                    idxs,
                    df.loc["Benchmark"].values,
                    linestyle="--",
                    linewidth=1.5,
                    color="red",
                )
                ax1.set_ylim(20, 130)
                # ax1.set_ylim(-500,500)
