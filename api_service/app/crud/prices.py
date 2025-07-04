from sqlalchemy.orm import Session
from sqlalchemy import text
from redis.client import Redis
from datetime import datetime

def get_history_prices(db: Session, ticker: str, skip: int = 0, limit: int = 500):
    query = text("""
        SELECT * FROM history_prices 
        WHERE ticker = :ticker 
        ORDER BY collect_date DESC 
        OFFSET :skip LIMIT :limit
    """)
    
    result = db.execute(query, {"ticker": ticker, "skip": skip, "limit": limit})
    return result.mappings().all()

def get_intraday_prices(redis_conn: Redis, ticker: str):
    if not redis_conn:
        return None
    redis_key = f'intraday:{ticker}'
    data = redis_conn.hgetall(redis_key)
    
    if data:
        for key, value in data.items():
            if key in ['open', 'high', 'low', 'last_price']:
                data[key] = float(value)
            elif key == 'last_volume':
                data[key] = int(value)
            elif key == 'last_update_utc':
                data[key] = datetime.fromisoformat(data[key])
        data['ticker'] = ticker
    return data