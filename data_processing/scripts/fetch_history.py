from typing import List, Literal

from datetime import datetime, timedelta, timezone
import pandas as pd

import yfinance as yf

from utils import FetchException
from db_manager import PostgreDBManager

from logger import *


def _extract_raw_data(tickers: List[str],
                     start_collect_date: datetime,
                     end_collect_date: datetime) -> pd.DataFrame:
    """Thực hiện thu thập dữ liệu của một list các cổ phiếu trong một khung thời gian"""
    _start_collect_date = start_collect_date.strftime('%Y-%m-%d')
    _end_collect_date = end_collect_date.strftime('%Y-%m-%d')
    raw_df = yf.Tickers(tickers).history(period='max', interval='1d',
                                         start=_start_collect_date,
                                         end=_end_collect_date,
                                         group_by='ticker',
                                         threads=False).swaplevel(0, 1, axis=1)
    if raw_df is None:
        raise FetchException('Error while fetch raw data from YFinance!')
    return raw_df

def _reconstruct_table(raw_df: pd.DataFrame, numeric_type: Literal['float32', 'float64']='float32'):
    """Thực hiện lại tái cấu trúc lại DataFrame đa cột, đồng thời chuyển đổi kiểu dữ liệu số."""
    stacked_df = raw_df.stack(level='Ticker', future_stack=True)
    stacked_df.reset_index(inplace=True)
    stacked_df.rename(columns={
        'Date': 'collect_date',
        'Ticker': 'ticker',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    }, inplace=True)
    
    cols = ['collect_date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
    stacked_df.columns.name = None
    
    for col in cols[2:]:
        stacked_df[col] = stacked_df[col].astype(numeric_type)
    
    return stacked_df[cols]

def _handle_missing_data(df: pd.DataFrame, 
                         start_date: datetime, end_date: datetime, 
                         features: List[str]):
    """Xử lý dữ liệu thiếu theo phương pháp ffill và bfill"""
    # Chuyển đổi datetime của Python sang Timestamp của Pandas
    pd_start_date = pd.Timestamp(start_date)
    pd_end_date = pd.Timestamp(end_date)
    
    # Xử lý missing data 
    df['collect_date'] = pd.to_datetime(df['collect_date'], utc=True)
    df[features] = df.groupby('ticker')[features].ffill().bfill()
    
    filtered_df = df[(df['collect_date'] >= pd_start_date) & (df['collect_date'] <= pd_end_date)]
    
    return filtered_df.copy()
    
def full_pipeline(table_name: str,
                  db_mng: PostgreDBManager):
    """Thực thi pipeline hoàn chỉnh để thu thập dữ liệu giá lịch sử hàng ngày.

    Quy trình bao gồm:
    1. Xác định khoảng thời gian cần lấy dữ liệu (từ ngày cuối cùng trong DB đến hôm qua).
    2. Gọi API của yfinance để lấy dữ liệu thô.
    3. Tái cấu trúc và làm sạch dữ liệu (xử lý giá trị thiếu).
    4. Ghi dữ liệu đã làm sạch vào cơ sở dữ liệu PostgreSQL.

    Args:
        table_name (str): Tên bảng trong CSDL để lưu dữ liệu (ví dụ: 'daily_prices').
        db_mng (PostgreDBManager): Instance của DB manager để tương tác với CSDL.
    """
    try:
        # 1. Xác định timing
        info('Identify time window to process ...')
        metadata = db_mng.get_active_tickers_with_info()
        tickers = list(metadata.keys())
        
        last_date = db_mng.get_last_history_date(table_name, tickers)
        start_date = last_date + timedelta(days=1)
            
        now_date = datetime.now(timezone.utc)      
        delta_day = 0
        if now_date.isoweekday() == 1:
            delta_day = 2
        elif now_date.isoweekday() == 7:
            delta_day = 1
            
        delta_day += 1

        end_date = datetime(now_date.year, now_date.month, now_date.day,
                            22, 0, 0, tzinfo=timezone.utc) - timedelta(days=delta_day)
        
        info(f'Start collect from {start_date} to {end_date} for {len(tickers)} tickers from Yahoo Finance API...')
        
        if start_date >= end_date:
            err('Invalid date')
            return
        
        start_collect_date = start_date - timedelta(days=30)
        end_collect_date = end_date + timedelta(days=delta_day)
        
        raw_df = _extract_raw_data(tickers, start_collect_date, end_collect_date)
        
        # 2. Transform
        info('Reconstructing and handling missing data ...')
        reconstructed_df = _reconstruct_table(raw_df, 'float32')
        cleaned_df = _handle_missing_data(reconstructed_df, start_date, end_date, features=['open', 'high', 'low', 'close', 'volume'])
        
        if cleaned_df.empty:
            err("Empty data after cleaning phase.")
            return

        # 3. Load
        info('Loading data into DB ...')
        selected_cols = ['collect_date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
        selected_df = cleaned_df[selected_cols].copy()
        db_mng.bulk_insert(table_name, selected_df, 
                           unique_cols=['collect_date', 'ticker'],
                           chunk_size=1000,
                           on_conflict='update')
        info(f"Successfully save {len(cleaned_df)} records.")
    except FetchException as e:
        err(f"A fetch exception occured: {e}")
    except Exception as e:
        err(f"An unknown exception occured: {e}")
    
if __name__ == '__main__':
    
    TABLE_NAME = 'daily_prices'
    
    db_mng = PostgreDBManager()
    
    full_pipeline(table_name=TABLE_NAME, db_mng=db_mng)
    
    
