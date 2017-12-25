import os
import pandas as pd
import numpy as np
import math
import copy
import pickle
import datetime as dt
import matplotlib.pyplot as plt
import sys
# Append the path of the directory one level above the current directory to import util
sys.path.append('../')
from util import *


def detect_return_diff(symbols, data_dict, symbol_change=-0.05, market_change=0.02):
    """ 
    Create the event dataframe. Here we are only interested in the opposite movements of 
    symbol and market, i.e. symbol_change and market_change are of opposite signs

    Parameters:
    symbols: A list of symbols of interest
    data_dict: A dictionary whose keys are types of data, e.g. Adj Close, Volume, etc. and 
    values are dataframes with dates as indices and symbols as columns
    symbol_change: Min.(if positive) or max. (if negative) change in the return of symbol
    market_change: Max.(if negative) or min. (if positive) change in the return of market
    
    Returns:
    df_events: A dataframe filled with either 1's for detected events or NAN's for no events
    """

    df_close = data_dict["Adj Close"]
    market_close = df_close["SPY"]

    # Create a dataframe filled with NAN's
    df_events = copy.deepcopy(df_close)
    df_events = df_events * np.NAN

    # Dates for the event range
    dates = df_close.index

    for symbol in symbols:
        for i in range(1, len(dates)):
            # Calculate the returns for this date
            symbol_return = (df_close[symbol].loc[dates[i]] / df_close[symbol].loc[dates[i - 1]]) - 1
            market_return = (market_close.loc[dates[i]] / market_close.loc[dates[i - 1]]) - 1

            # Event is found if both the symbol and market cross their respective thresholds
            if symbol_change < 0 and market_change > 0:
                if symbol_return <= symbol_change and market_return >= market_change:
                    df_events[symbol].loc[dates[i]] = 1
            elif symbol_change > 0 and market_change < 0:
                if symbol_return >= symbol_change and market_return <= market_change:
                    df_events[symbol].loc[dates[i]] = 1
            else:
                print ("Here we are only interested in the opposite movements of symbol and market, \
                    i.e. you should ensure symbol_change and market_change are of opposite signs")
    return df_events


def plot_return_diff_events(df_events_input, data_dict, num_backward=20, num_forward=20,
                output_filename="event_chart", market_neutral=True, error_bars=True,
                market_sym="SPY"):
    """ 
    Plot a chart of the events found by detect_return_diff

    Parameters:
    df_events_input: A dataframe filled with 1's for detected events or NAN's for no events
    data_dict: A dictionary whose keys are types of data, e.g. Adj Close, Volume, etc. and 
    values are dataframes with dates as indices and symbols as columns
    num_backward: Number of periods to look back
    num_forward: Number of periods to look ahead
    output_filename: Name of output file
    market_neutral: True/False - whether to exclude market return from stock return
    error_bars: True/False - whether to show error bars, i.e. standard deviations
    market_sym: Symbol of the market index
    
    Returns:
    A pdf file plotting the means and standard deviations of the returns the date range of 
    [num_backward, num_forward], including the event day
    """

    df_events = df_events_input.copy()
    
    # Compute daily return
    df_returns = compute_daily_returns(data_dict["Adj Close"])

    if market_neutral == True:
        # Substract market returns from all returns of all symbols
        df_returns = df_returns.sub(df_returns[market_sym].values, axis=0)
        del df_returns[market_sym]
        del df_events[market_sym]

    # Since we want to look back num_backward rows and ahead num_forward dates of the event,
    # we ignore the first num_backward and last num_forward rows, and replace them with NAN's
    df_events.values[0:num_backward, :] = np.NaN
    if num_forward > 0:
        df_events.values[-num_forward:, :] = np.NaN

    # Number of events
    num_events = int(df_events.count().sum())
    assert num_events > 0, "Zero events in the event matrix"
    all_events_returns = []

    # Look for the events and add them to a numpy ndarray which has shape of
    # (num_events, num_backward days before event + 1 event day + num_forward days after event)
    for symbol in df_events.columns:
        for j, event_date in enumerate(df_events.index):
            if df_events[symbol][event_date] == 1:
                single_event_returns = df_returns[symbol][j - num_backward:j + 1 + num_forward]
                if type(all_events_returns) == type([]):
                    all_events_returns = single_event_returns
                else:
                    all_events_returns = np.vstack((all_events_returns, single_event_returns))

    # If there is only 1 event, ensure that the ndarray has the above mentioned shape
    if len(all_events_returns.shape) == 1:
        all_events_returns = np.expand_dims(all_events_returns, axis=0)

    print (num_events, all_events_returns.shape)
    # Compute cumulative product returns
    all_events_returns = np.cumprod(all_events_returns + 1, axis=1)

    # Normalize cumulative returns by event day
    all_events_returns = (all_events_returns.T / all_events_returns[:, num_backward]).T

    # Compute the means and standard deviations
    mean_returns = np.mean(all_events_returns, axis=0)
    std_returns = np.std(all_events_returns, axis=0)

    # The date range to be used as the x-axis
    x_axis_range = range(-num_backward, num_forward + 1)

    # Plot the chart
    plt.clf()
    plt.axhline(y=1.0, xmin=-num_backward, xmax=num_forward, color="k")
    if error_bars == True:
        plt.errorbar(x_axis_range[num_backward:], mean_returns[num_backward:],
                    yerr=std_returns[num_backward:], ecolor="r")
    plt.plot(x_axis_range, mean_returns, linewidth=3, label="mean", color="b")
    plt.xlim(-num_backward - 1, num_forward + 1)
    if market_neutral == True:
        plt.title("Market relative mean return of {} events".format(num_events))
    else:
        plt.title("Mean return of {} events".format(num_events))
    plt.xlabel("Days")
    plt.ylabel("Cumulative Returns")
    plt.savefig(output_filename, format="pdf")

