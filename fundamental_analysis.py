"""
Fundamental Analysis Script
Analyzes your current holdings to identify fundamentally strong stocks
with good probability of returns.
"""
import json
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

# ETF symbols that don't have traditional fundamental metrics
ETF_SYMBOLS = ['GOLDBEES-EQ', 'SILVERBEES-EQ', 'NIFTYBEES-EQ', 'BANKBEES-EQ', 
               'SILVERIETF-EQ', 'HDFCGOLD-EQ', 'LIQUIDCASE-EQ', 'BHARTIHEXA-EQ']

def convert_symbol_to_yfinance(symbol: str) -> str:
    """Convert NSE symbol format to yfinance format."""
    # Remove -EQ suffix
    base_symbol = symbol.replace('-EQ', '')
    # Add .NS for NSE
    return f"{base_symbol}.NS"

def get_fundamental_data(symbol: str) -> Optional[Dict]:
    """Fetch fundamental data for a stock using yfinance."""
    try:
        yf_symbol = convert_symbol_to_yfinance(symbol)
        ticker = yf.Ticker(yf_symbol)
        
        # Get info
        info = ticker.info
        
        # Get financials
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow
        
        # Get historical data for growth calculations
        hist = ticker.history(period="2y")
        
        data = {
            'symbol': symbol,
            'name': info.get('longName', info.get('shortName', symbol)),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            
            # Valuation metrics
            'pe_ratio': info.get('trailingPE', None),
            'forward_pe': info.get('forwardPE', None),
            'pb_ratio': info.get('priceToBook', None),
            'peg_ratio': info.get('pegRatio', None),
            'price_to_sales': info.get('priceToSalesTrailing12Months', None),
            'ev_to_ebitda': info.get('enterpriseToEbitda', None),
            
            # Profitability
            'roe': info.get('returnOnEquity', None),
            'roa': info.get('returnOnAssets', None),
            'profit_margin': info.get('profitMargins', None),
            'operating_margin': info.get('operatingMargins', None),
            'gross_margin': info.get('grossMargins', None),
            
            # Financial health
            'debt_to_equity': info.get('debtToEquity', None),
            'current_ratio': info.get('currentRatio', None),
            'quick_ratio': info.get('quickRatio', None),
            'total_debt': info.get('totalDebt', None),
            'total_cash': info.get('totalCash', None),
            
            # Growth
            'revenue_growth': info.get('revenueGrowth', None),
            'earnings_growth': info.get('earningsGrowth', None),
            'earnings_quarterly_growth': info.get('earningsQuarterlyGrowth', None),
            
            # Market metrics
            'market_cap': info.get('marketCap', None),
            'enterprise_value': info.get('enterpriseValue', None),
            'dividend_yield': info.get('dividendYield', None),
            'beta': info.get('beta', None),
            
            # Price metrics
            'current_price': info.get('currentPrice', None),
            '52_week_high': info.get('fiftyTwoWeekHigh', None),
            '52_week_low': info.get('fiftyTwoWeekLow', None),
            'price_to_52w_high': None,
            'price_to_52w_low': None,
            
            # Additional
            'book_value': info.get('bookValue', None),
            'eps': info.get('trailingEps', None),
            'forward_eps': info.get('forwardEps', None),
        }
        
        # Calculate price position in 52-week range
        if data['current_price'] and data['52_week_high'] and data['52_week_low']:
            if data['52_week_high'] > data['52_week_low']:
                data['price_to_52w_high'] = (data['current_price'] - data['52_week_low']) / (data['52_week_high'] - data['52_week_low'])
        
        # Try to get growth from financials if not in info
        if data['revenue_growth'] is None and financials is not None and not financials.empty:
            try:
                revenue = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else None
                if revenue is not None and len(revenue) >= 2:
                    rev_growth = ((revenue.iloc[0] - revenue.iloc[1]) / abs(revenue.iloc[1])) * 100
                    data['revenue_growth'] = rev_growth
            except:
                pass
        
        return data
    except Exception as e:
        print(f"   ⚠️ Error fetching data for {symbol}: {e}")
        return None

def calculate_fundamental_score(data: Dict, is_etf: bool = False) -> Dict:
    """Calculate a fundamental score (0-100) for a stock."""
    if is_etf:
        # ETFs are scored differently - mainly on expense ratio, AUM, tracking error
        return {
            'total_score': 70,  # Default neutral score for ETFs
            'scores': {
                'valuation': 70,
                'profitability': 70,
                'financial_health': 70,
                'growth': 70,
            },
            'recommendation': 'HOLD',
            'reason': 'ETF - Fundamental analysis limited. Focus on expense ratio and tracking error.'
        }
    
    scores = {
        'valuation': 50,  # Base score
        'profitability': 50,
        'financial_health': 50,
        'growth': 50,
    }
    
    # Valuation Score (Lower P/E, P/B is better, but not too low)
    pe = data.get('pe_ratio')
    pb = data.get('pb_ratio')
    peg = data.get('peg_ratio')
    
    if pe:
        if 10 <= pe <= 25:
            scores['valuation'] += 15  # Good range
        elif 5 <= pe < 10:
            scores['valuation'] += 10  # Very cheap, might be value trap
        elif 25 < pe <= 35:
            scores['valuation'] += 5   # Slightly expensive
        elif pe > 35:
            scores['valuation'] -= 10  # Overvalued
        elif pe < 5:
            scores['valuation'] -= 5   # Might be too cheap (value trap)
    
    if pb:
        if 1 <= pb <= 3:
            scores['valuation'] += 10
        elif pb > 5:
            scores['valuation'] -= 10
        elif pb < 0.5:
            scores['valuation'] -= 5
    
    if peg:
        if 0.5 <= peg <= 1.5:
            scores['valuation'] += 10  # Good PEG
        elif peg > 2:
            scores['valuation'] -= 5
    
    # Profitability Score
    roe = data.get('roe')
    roa = data.get('roa')
    profit_margin = data.get('profit_margin')
    operating_margin = data.get('operating_margin')
    
    if roe:
        if roe > 20:
            scores['profitability'] += 20
        elif roe > 15:
            scores['profitability'] += 15
        elif roe > 10:
            scores['profitability'] += 10
        elif roe < 5:
            scores['profitability'] -= 15
    
    if roa:
        if roa > 10:
            scores['profitability'] += 10
        elif roa > 5:
            scores['profitability'] += 5
        elif roa < 2:
            scores['profitability'] -= 10
    
    if profit_margin:
        if profit_margin > 0.20:  # 20%
            scores['profitability'] += 15
        elif profit_margin > 0.10:  # 10%
            scores['profitability'] += 10
        elif profit_margin < 0:
            scores['profitability'] -= 20
    
    if operating_margin:
        if operating_margin > 0.15:
            scores['profitability'] += 10
        elif operating_margin < 0:
            scores['profitability'] -= 15
    
    # Financial Health Score
    debt_to_equity = data.get('debt_to_equity')
    current_ratio = data.get('current_ratio')
    quick_ratio = data.get('quick_ratio')
    
    if debt_to_equity is not None:
        if debt_to_equity < 0.5:
            scores['financial_health'] += 20  # Low debt
        elif debt_to_equity < 1.0:
            scores['financial_health'] += 10
        elif debt_to_equity > 2.0:
            scores['financial_health'] -= 15  # High debt
    
    if current_ratio:
        if 1.5 <= current_ratio <= 3.0:
            scores['financial_health'] += 15
        elif current_ratio < 1.0:
            scores['financial_health'] -= 20  # Liquidity issues
        elif current_ratio > 5:
            scores['financial_health'] -= 5  # Too much cash, inefficient
    
    if quick_ratio:
        if quick_ratio > 1.0:
            scores['financial_health'] += 10
        elif quick_ratio < 0.5:
            scores['financial_health'] -= 10
    
    # Growth Score
    revenue_growth = data.get('revenue_growth')
    earnings_growth = data.get('earnings_growth')
    
    if revenue_growth:
        if revenue_growth > 0.20:  # 20%+
            scores['growth'] += 20
        elif revenue_growth > 0.10:  # 10%+
            scores['growth'] += 15
        elif revenue_growth > 0.05:  # 5%+
            scores['growth'] += 10
        elif revenue_growth < 0:
            scores['growth'] -= 15
    
    if earnings_growth:
        if earnings_growth > 0.25:  # 25%+
            scores['growth'] += 20
        elif earnings_growth > 0.15:  # 15%+
            scores['growth'] += 15
        elif earnings_growth < 0:
            scores['growth'] -= 20
    
    # Calculate total score
    total_score = sum(scores.values()) / len(scores)
    
    # Determine recommendation
    if total_score >= 75:
        recommendation = 'STRONG BUY'
        reason = 'Excellent fundamentals across all metrics'
    elif total_score >= 65:
        recommendation = 'BUY'
        reason = 'Good fundamentals with strong potential'
    elif total_score >= 55:
        recommendation = 'HOLD'
        reason = 'Moderate fundamentals, monitor closely'
    elif total_score >= 45:
        recommendation = 'WEAK HOLD'
        reason = 'Below average fundamentals, consider exit'
    else:
        recommendation = 'SELL'
        reason = 'Poor fundamentals, high risk'
    
    return {
        'total_score': round(total_score, 2),
        'scores': {k: round(v, 2) for k, v in scores.items()},
        'recommendation': recommendation,
        'reason': reason
    }

def analyze_portfolio():
    """Main function to analyze all positions."""
    print("=" * 80)
    print("📊 FUNDAMENTAL ANALYSIS OF PORTFOLIO")
    print("=" * 80)
    print()
    
    # Load positions
    try:
        with open('logs/positions.json', 'r') as f:
            positions_data = json.load(f)
        positions = positions_data.get('positions', [])
    except Exception as e:
        print(f"❌ Error loading positions: {e}")
        return
    
    if not positions:
        print("⚠️ No positions found in positions.json")
        return
    
    print(f"📋 Found {len(positions)} positions to analyze")
    print()
    
    results = []
    
    for idx, pos in enumerate(positions, 1):
        symbol = pos.get('symbol')
        quantity = pos.get('quantity', 0)
        buy_price = pos.get('buy_price', 0)
        current_price = pos.get('current_price', 0)
        
        if not symbol:
            continue
        
        print(f"[{idx}/{len(positions)}] Analyzing {symbol}...")
        
        is_etf = symbol in ETF_SYMBOLS
        
        # Get fundamental data
        data = get_fundamental_data(symbol)
        
        if not data:
            print(f"   ⚠️ Could not fetch data for {symbol}")
            results.append({
                'symbol': symbol,
                'error': 'Data not available'
            })
            continue
        
        # Calculate score
        score_data = calculate_fundamental_score(data, is_etf)
        
        # Calculate position metrics
        investment_value = quantity * buy_price if buy_price else 0
        current_value = quantity * current_price if current_price else 0
        pnl = current_value - investment_value
        pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price and buy_price > 0 else 0
        
        result = {
            'symbol': symbol,
            'name': data.get('name', symbol),
            'sector': data.get('sector', 'Unknown'),
            'quantity': quantity,
            'buy_price': buy_price,
            'current_price': current_price,
            'investment_value': investment_value,
            'current_value': current_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'fundamental_score': score_data['total_score'],
            'recommendation': score_data['recommendation'],
            'reason': score_data['reason'],
            'scores': score_data['scores'],
            'metrics': {
                'pe_ratio': data.get('pe_ratio'),
                'pb_ratio': data.get('pb_ratio'),
                'roe': data.get('roe'),
                'debt_to_equity': data.get('debt_to_equity'),
                'revenue_growth': data.get('revenue_growth'),
                'profit_margin': data.get('profit_margin'),
                'market_cap': data.get('market_cap'),
            },
            'is_etf': is_etf
        }
        
        results.append(result)
        
        print(f"   ✅ {data.get('name', symbol)} - Score: {score_data['total_score']:.1f}/100 - {score_data['recommendation']}")
        print()
    
    # Sort by fundamental score (descending)
    results.sort(key=lambda x: x.get('fundamental_score', 0) if 'fundamental_score' in x else 0, reverse=True)
    
    # Print summary
    print("=" * 80)
    print("📊 FUNDAMENTAL ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    
    # Group by recommendation
    strong_buy = [r for r in results if r.get('recommendation') == 'STRONG BUY']
    buy = [r for r in results if r.get('recommendation') == 'BUY']
    hold = [r for r in results if r.get('recommendation') == 'HOLD']
    weak_hold = [r for r in results if r.get('recommendation') == 'WEAK HOLD']
    sell = [r for r in results if r.get('recommendation') == 'SELL']
    
    print("🟢 STRONG BUY (Score ≥75):")
    for r in strong_buy:
        print(f"   • {r['symbol']:20s} | {r['name'][:40]:40s} | Score: {r['fundamental_score']:.1f} | P&L: {r['pnl_pct']:+.1f}%")
    print()
    
    print("🟡 BUY (Score 65-74):")
    for r in buy:
        print(f"   • {r['symbol']:20s} | {r['name'][:40]:40s} | Score: {r['fundamental_score']:.1f} | P&L: {r['pnl_pct']:+.1f}%")
    print()
    
    print("⚪ HOLD (Score 55-64):")
    for r in hold:
        print(f"   • {r['symbol']:20s} | {r['name'][:40]:40s} | Score: {r['fundamental_score']:.1f} | P&L: {r['pnl_pct']:+.1f}%")
    print()
    
    print("🟠 WEAK HOLD (Score 45-54):")
    for r in weak_hold:
        print(f"   • {r['symbol']:20s} | {r['name'][:40]:40s} | Score: {r['fundamental_score']:.1f} | P&L: {r['pnl_pct']:+.1f}%")
    print()
    
    print("🔴 SELL (Score <45):")
    for r in sell:
        print(f"   • {r['symbol']:20s} | {r['name'][:40]:40s} | Score: {r['fundamental_score']:.1f} | P&L: {r['pnl_pct']:+.1f}%")
    print()
    
    # Detailed table
    print("=" * 80)
    print("📋 DETAILED ANALYSIS TABLE")
    print("=" * 80)
    print()
    
    print(f"{'Symbol':<15} {'Name':<30} {'Score':<8} {'P/E':<8} {'P/B':<8} {'ROE%':<8} {'D/E':<8} {'Rec':<12} {'P&L%':<8}")
    print("-" * 120)
    
    for r in results:
        if 'error' in r:
            continue
        
        pe = f"{r['metrics']['pe_ratio']:.1f}" if r['metrics']['pe_ratio'] else "N/A"
        pb = f"{r['metrics']['pb_ratio']:.1f}" if r['metrics']['pb_ratio'] else "N/A"
        roe = f"{r['metrics']['roe']*100:.1f}" if r['metrics']['roe'] else "N/A"
        de = f"{r['metrics']['debt_to_equity']:.2f}" if r['metrics']['debt_to_equity'] is not None else "N/A"
        
        name = r['name'][:28] if len(r['name']) > 28 else r['name']
        
        print(f"{r['symbol']:<15} {name:<30} {r['fundamental_score']:<8.1f} {pe:<8} {pb:<8} {roe:<8} {de:<8} {r['recommendation']:<12} {r['pnl_pct']:>+7.1f}%")
    
    print()
    print("=" * 80)
    print("💡 KEY INSIGHTS")
    print("=" * 80)
    print()
    
    # Top performers
    top_3 = [r for r in results if 'fundamental_score' in r][:3]
    if top_3:
        print("🏆 TOP 3 FUNDAMENTALLY STRONG STOCKS:")
        for i, r in enumerate(top_3, 1):
            print(f"   {i}. {r['symbol']} ({r['name']}) - Score: {r['fundamental_score']:.1f}")
            print(f"      Reason: {r['reason']}")
            pe_val = f"{r['metrics']['pe_ratio']:.1f}" if r['metrics']['pe_ratio'] else "N/A"
            roe_val = f"{r['metrics']['roe']*100:.1f}%" if r['metrics']['roe'] else "N/A"
            de_val = f"{r['metrics']['debt_to_equity']:.2f}" if r['metrics']['debt_to_equity'] is not None else "N/A"
            print(f"      Metrics: P/E={pe_val}, ROE={roe_val}, Debt/Equity={de_val}")
        print()
    
    # Underperformers
    bottom_3 = [r for r in results if 'fundamental_score' in r][-3:]
    if bottom_3:
        print("⚠️ STOCKS WITH WEAK FUNDAMENTALS:")
        for i, r in enumerate(bottom_3, 1):
            print(f"   {i}. {r['symbol']} ({r['name']}) - Score: {r['fundamental_score']:.1f}")
            print(f"      Reason: {r['reason']}")
        print()
    
    # Sector analysis
    sectors = {}
    for r in results:
        if 'error' in r:
            continue
        sector = r.get('sector', 'Unknown')
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(r)
    
    if sectors:
        print("📊 SECTOR BREAKDOWN:")
        for sector, stocks in sectors.items():
            avg_score = sum(s.get('fundamental_score', 0) for s in stocks) / len(stocks)
            print(f"   • {sector}: {len(stocks)} stocks, Avg Score: {avg_score:.1f}")
        print()
    
    print("=" * 80)
    print("✅ Analysis Complete!")
    print("=" * 80)

if __name__ == "__main__":
    analyze_portfolio()
