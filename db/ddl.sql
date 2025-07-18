CREATE TABLE IF NOT EXISTS public.daily_prices ( 
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    "open" float4 NULL, high float4 NULL, 
    low float4 NULL, "close" float4 NULL, 
    volume float4 NULL, ticker varchar(10) NOT NULL, 
    collect_date timestamp with time zone NOT NULL, 
    foreign key (ticker) references tickers(ticker_sym),
    CONSTRAINT daily_prices_unique UNIQUE (ticker, collect_date)
);

CREATE TABLE IF NOT EXISTS public.relevant_news ( 
    news_uuid varchar(256) PRIMARY KEY,
    ticker varchar(10) not null,
    title TEXT not null,
    summary TEXT null,
    provider varchar(150) null,
    link TEXT null,
    publish_time timestamp with time zone null,
    collect_time timestamp with time zone not null,
    foreign key (ticker) references tickers(ticker_sym)
);

create table if not exists public.exchanges (
	exchange_code varchar(15) primary key,
	exchange_name varchar(300) null,
	currency varchar(7) not null,
	timezone varchar(60) not null,
	country varchar(50) not null
)

create table if not exists public.sectors (
	sector_code varchar(7) primary key,
	sector_name varchar(50) null
)

create table if not exists public.tickers (
	ticker_sym varchar(10) primary key,
	company_name varchar(255) null,
	exchange_code varchar(15) not null,
	sector_code varchar(7) not null,
	is_active boolean null default TRUE,
	
	foreign key (exchange_code) references exchanges(exchange_code),
	foreign key (sector_code) references sectors(sector_code)
)