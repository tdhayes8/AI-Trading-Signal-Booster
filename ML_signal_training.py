import pandas as pd
from sklearn.model_selection import train_test_split
import os



folder = './data'
dfs = []
for file in os.listdir(folder):
    df = pd.read_excel(f'{file}') # maybe just file instead of extra string
    df['strategy'] = f'{file}' #same ^
    dfs.append(df)
all_trades = pd.concat(dfs, ignore_index=True)
entries = all_trades[all_trades['Type'].str.contains('Entry')]

#Need to loop through and add a column and add a list at that column 
#of which other signals are in at that point

X = entries[["strategy", "newListCOLUMN" , "feature3"]]
#y should be predicting the profit based on the strategies in at this point, or those that have gotten out, etc.
#could be a boolean of making a certain amount, or a profit
#maybe wait for certain profits and buy once expectation goes above a certain amount,
#and sell if it goes below a certain amount
y = all_trades["P&L %"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)