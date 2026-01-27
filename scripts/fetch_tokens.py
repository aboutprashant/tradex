import requests
import pandas as pd

def download_tokens():
    print("Downloading symbol tokens from Angel One...")
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPISymbolTokendetails.json"
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data)
    return df

def search_token(symbol_name):
    df = download_tokens()
    # Search for symbol in NSE (Cash segment)
    result = df[(df['symbol'].str.contains(symbol_name, case=False)) & (df['exch_seg'] == 'NSE')]
    
    if not result.empty:
        print("\nMatching Symbols found in NSE:")
        print(result[['symbol', 'token', 'exch_seg']])
    else:
        print(f"No matching symbol found for '{symbol_name}'")

if __name__ == "__main__":
    symbol = input("Enter Stock Name (e.g. NIFTYBEES, RELIANCE): ").upper()
    search_token(symbol)
