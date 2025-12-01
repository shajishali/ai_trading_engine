"""
Real Price Service - Fetches live cryptocurrency prices from external APIs
"""

import requests
import logging
import time
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RealPriceService:
    """Service for fetching real cryptocurrency prices"""
    
    def __init__(self):
        self.binance_api = "https://api.binance.com/api/v3"
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.cache_timeout = 300  # Cache prices for 5 minutes instead of 30 seconds
        
        # Supported symbols for live data - 200+ popular cryptocurrencies
        self.live_symbols = [
            # Top 20 by Market Cap
            'BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'USDC', 'XRP', 'STETH', 'ADA', 'AVAX',
            'DOGE', 'TRX', 'LINK', 'DOT', 'MATIC', 'TON', 'SHIB', 'DAI', 'UNI', 'BCH',
            
            # Major Altcoins
            'LTC', 'XLM', 'ATOM', 'ETC', 'FIL', 'NEAR', 'APT', 'OP', 'ARB', 'MKR',
            'VET', 'ICP', 'ALGO', 'FTM', 'THETA', 'XMR', 'HBAR', 'IMX', 'STX', 'GRT',
            
            # DeFi & Gaming
            'AAVE', 'COMP', 'CRV', 'SUSHI', 'YFI', 'SNX', 'BAL', 'REN', 'KNC', 'ZRX',
            'MANA', 'SAND', 'AXS', 'ENJ', 'CHZ', 'GALA', 'ROSE', 'ONE', 'HOT', 'BAT',
            
            # Layer 1 & 2
            'SUI', 'SEI', 'TIA', 'INJ', 'KAS', 'RUNE', 'FLOW', 'EGLD', 'ZIL', 'QTUM',
            'NEO', 'WAVES', 'XTZ', 'IOTA', 'NANO', 'XEM', 'VTHO', 'ICX', 'ONT', 'ZEN',
            
            # Exchange Tokens
            'OKB', 'HT', 'GT', 'KCS', 'BTT', 'CRO', 'FTT', 'LEO', 'HOT', 'BNT',
            
            # Meme & Social
            'PEPE', 'FLOKI', 'BONK', 'WIF', 'MYRO', 'POPCAT', 'BOOK', 'TURBO', 'SPX', 'BOME',
            'SLERF', 'CAT', 'DOG', 'MOON', 'ROCKET', 'LAMBO', 'YACHT', 'PLANET', 'STAR', 'GEM',
            
            # AI & Tech
            'FET', 'OCEAN', 'AGIX', 'RNDR', 'AKT', 'HFT', 'TAO', 'BITTENSOR', 'AI', 'GPT',
            'CHAT', 'BOT', 'ROBOT', 'NEURAL', 'BRAIN', 'MIND', 'THINK', 'LOGIC', 'SMART', 'GENIUS',
            
            # Privacy & Security
            'XMR', 'ZEC', 'DASH', 'XHV', 'BEAM', 'GRIN', 'PIVX', 'FIRO', 'XVG', 'ZEN',
            
            # Oracle & Data
            'BAND', 'API3', 'DIA', 'LINK', 'NEST', 'PENDLE', 'PERP', 'DYDX', 'GMX', 'SNX',
            
            # Metaverse & NFT
            'MANA', 'SAND', 'AXS', 'ENJ', 'CHZ', 'GALA', 'ROSE', 'ONE', 'HOT', 'BAT',
            'APE', 'DYDX', 'IMX', 'OP', 'ARB', 'MATIC', 'POLYGON', 'AVAX', 'FTM', 'SOL',
            
            # Additional Popular Coins
            'CAKE', 'BAKE', 'SXP', 'WIN', 'BTT', 'TRX', 'JST', 'SUN', 'BUSD', 'USDD',
            'TUSD', 'FRAX', 'LUSD', 'GUSD', 'PAX', 'USDP', 'BUSD', 'USDC', 'DAI', 'USDT',
            
            # More Altcoins
            'RVN', 'ERG', 'XDC', 'XRP', 'XLM', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE',
            'COMP', 'MKR', 'YFI', 'SNX', 'BAL', 'REN', 'KNC', 'ZRX', 'CRV', 'SUSHI',
            
            # Additional 50+ coins to reach 200+
            'ANKR', 'AR', 'AUDIO', 'BICO', 'BLZ', 'BNT', 'BOND', 'C98', 'CELO', 'CFX',
            'CHR', 'CLV', 'COCOS', 'CTSI', 'CTXC', 'CVP', 'DENT', 'DGB', 'DUSK', 'ELF',
            'ERN', 'FIDA', 'FLOW', 'FORTH', 'FRONT', 'FTM', 'FXS', 'GALA', 'GLM', 'GMT',
            'GODS', 'GOG', 'GRT', 'GTC', 'HFT', 'HIGH', 'HIVE', 'HOPR', 'ICP', 'IDEX',
            'ILV', 'IMX', 'INJ', 'IOTX', 'IRIS', 'JASMY', 'JOE', 'KAVA', 'KDA', 'KEY',
            'KLAY', 'KSM', 'LDO', 'LINA', 'LIT', 'LOKA', 'LPT', 'LQTY', 'LRC', 'MASK',
            'MINA', 'MKR', 'MLN', 'MOCA', 'MOVR', 'MTL', 'MULTI', 'NEO', 'NKN', 'NMR',
            'OCEAN', 'OGN', 'OM', 'ONG', 'ONT', 'OP', 'ORBS', 'OXT', 'PAXG', 'PEOPLE',
            'PERP', 'PHA', 'PLA', 'POLS', 'POLY', 'POND', 'POWR', 'PRO', 'PROM', 'QNT',
            'QUICK', 'RAD', 'RARE', 'RARI', 'RAY', 'RBN', 'REN', 'REP', 'REQ', 'RLC',
            'ROSE', 'RSR', 'RSS3', 'RUNE', 'SAND', 'SCRT', 'SFP', 'SHIB', 'SKL', 'SLP',
            'SNT', 'SNX', 'SOC', 'SPELL', 'SRM', 'STG', 'STMX', 'STORJ', 'STPT', 'STRAX',
            'SUPER', 'SUSHI', 'SWAP', 'SWEAT', 'SXP', 'SYN', 'SYS', 'T', 'TFUEL', 'THETA',
            'TLM', 'TOKE', 'TOMO', 'TORN', 'TRB', 'TRIBE', 'TRU', 'TRX', 'TUSD', 'TVK',
            'UMA', 'UNI', 'USDC', 'USDD', 'USDT', 'UTK', 'VET', 'VGX', 'VRA', 'VTHO',
            'WAVES', 'WAXL', 'WAXP', 'WBTC', 'WOO', 'XDC', 'XEC', 'XEM', 'XLM', 'XMR',
            'XRP', 'XTZ', 'XVG', 'YFI', 'YGG', 'ZEC', 'ZEN', 'ZIL', 'ZRX', '1INCH'
        ]
    
    def get_live_prices(self):
        """Get live cryptocurrency prices from multiple sources"""
        try:
            # Try to get from cache first
            cached_prices = cache.get('live_crypto_prices')
            if cached_prices:
                logger.debug("Returning cached prices")
                return cached_prices
            
            # Fetch from Binance API
            binance_prices = self._fetch_binance_prices()
            
            # Fetch from CoinGecko API
            coingecko_prices = self._fetch_coingecko_prices()
            
            # Merge prices (Binance takes priority for USDT pairs)
            live_prices = {}
            
            # Add Binance prices
            for symbol, data in binance_prices.items():
                if symbol in self.live_symbols:
                    live_prices[symbol] = data
            
            # Add CoinGecko prices for missing symbols
            for symbol, data in coingecko_prices.items():
                if symbol in self.live_symbols and symbol not in live_prices:
                    live_prices[symbol] = data
            
            # Cache the results
            cache.set('live_crypto_prices', live_prices, self.cache_timeout)
            
            logger.info(f"Fetched live prices for {len(live_prices)} symbols")
            return live_prices
            
        except Exception as e:
            logger.error(f"Error fetching live prices: {e}")
            # Return cached prices if available, otherwise empty dict
            return cache.get('live_crypto_prices', {})
    
    def _fetch_binance_prices(self):
        """Fetch prices from Binance API"""
        try:
            url = f"{self.binance_api}/ticker/24hr"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                prices = {}
                
                for ticker in data:
                    symbol = ticker['symbol']
                    
                    # Only process USDT pairs for major coins
                    if symbol.endswith('USDT'):
                        base_symbol = symbol[:-4]  # Remove 'USDT'
                        
                        if base_symbol in self.live_symbols:
                            price = float(ticker['lastPrice'])
                            change_24h = float(ticker['priceChangePercent'])
                            volume_24h = float(ticker['volume'])
                            
                            prices[base_symbol] = {
                                'price': price,
                                'change_24h': change_24h,
                                'volume_24h': volume_24h,
                                'source': 'Binance',
                                'last_updated': timezone.now().isoformat()
                            }
                
                return prices
            else:
                logger.warning(f"Binance API returned status {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching Binance prices: {e}")
            return {}
    
    def _fetch_coingecko_prices(self):
        """Fetch prices from CoinGecko API"""
        try:
            coin_ids = self._get_coingecko_ids()
            
            # CoinGecko API has a limit on the number of coin IDs per request
            # Split into batches of 50 to avoid 400 errors
            max_ids_per_request = 50
            all_prices = {}
            
            for i in range(0, len(coin_ids), max_ids_per_request):
                batch_ids = coin_ids[i:i + max_ids_per_request]
                url = f"{self.coingecko_api}/simple/price"
                params = {
                    'ids': ','.join(batch_ids),
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                    'include_24hr_vol': 'true'
                }
                
                try:
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for coin_id, coin_data in data.items():
                            symbol = self._coingecko_id_to_symbol(coin_id)
                            if symbol in self.live_symbols:
                                price = coin_data.get('usd', 0)
                                change_24h = coin_data.get('usd_24h_change', 0)
                                volume_24h = coin_data.get('usd_24h_vol', 0)
                                
                                all_prices[symbol] = {
                                    'price': price,
                                    'change_24h': change_24h,
                                    'volume_24h': volume_24h,
                                    'source': 'CoinGecko',
                                    'last_updated': timezone.now().isoformat()
                                }
                    else:
                        # Log detailed error information
                        error_msg = f"CoinGecko API batch {i//max_ids_per_request + 1} returned status {response.status_code}"
                        try:
                            error_body = response.json()
                            error_msg += f" - {error_body}"
                        except:
                            error_msg += f" - {response.text[:200]}"
                        logger.warning(f"{error_msg} | Batch coin IDs: {len(batch_ids)} coins")
                    
                    # Small delay between batches to avoid rate limiting
                    if i + max_ids_per_request < len(coin_ids):
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"Error fetching CoinGecko batch {i//max_ids_per_request + 1}: {e}")
                    continue
            
            return all_prices
                
        except Exception as e:
            logger.error(f"Error fetching CoinGecko prices: {e}")
            return {}
    
    def get_symbol_price(self, symbol):
        """Get price for a specific symbol"""
        prices = self.get_live_prices()
        return prices.get(symbol, {})
    
    def refresh_prices(self):
        """Force refresh of prices (clear cache)"""
        cache.delete('live_crypto_prices')
        return self.get_live_prices()
    
    @staticmethod
    def _extract_base_symbol(symbol):
        """Extract base symbol from trading pair (e.g., BTCUSDT -> BTC)"""
        quote_currencies = ['USDT', 'BTC', 'ETH', 'BNB', 'USD']
        
        for quote in quote_currencies:
            if symbol.endswith(quote):
                return symbol[:-len(quote)]
        
        return symbol
    
    @staticmethod
    def _get_coingecko_ids():
        """Get CoinGecko coin IDs for supported symbols"""
        # Comprehensive mapping of symbols to CoinGecko IDs
        symbol_to_id = {
            # Top 20 by Market Cap
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'USDT': 'tether',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'USDC': 'usd-coin',
            'XRP': 'ripple',
            'STETH': 'staked-ether',
            'ADA': 'cardano',
            'AVAX': 'avalanche-2',
            'DOGE': 'dogecoin',
            'TRX': 'tron',
            'LINK': 'chainlink',
            'DOT': 'polkadot',
            'MATIC': 'matic-network',
            'TON': 'the-open-network',
            'SHIB': 'shiba-inu',
            'DAI': 'dai',
            'UNI': 'uniswap',
            'BCH': 'bitcoin-cash',
            
            # Major Altcoins
            'LTC': 'litecoin',
            'XLM': 'stellar',
            'ATOM': 'cosmos',
            'ETC': 'ethereum-classic',
            'FIL': 'filecoin',
            'NEAR': 'near',
            'APT': 'aptos',
            'OP': 'optimism',
            'ARB': 'arbitrum',
            'MKR': 'maker',
            'VET': 'vechain',
            'ICP': 'internet-computer',
            'ALGO': 'algorand',
            'FTM': 'fantom',
            'THETA': 'theta-token',
            'XMR': 'monero',
            'HBAR': 'hedera-hashgraph',
            'IMX': 'immutable-x',
            'STX': 'blockstack',
            'GRT': 'the-graph',
            
            # DeFi & Gaming
            'AAVE': 'aave',
            'COMP': 'compound-governance-token',
            'CRV': 'curve-dao-token',
            'SUSHI': 'sushi',
            'YFI': 'yearn-finance',
            'SNX': 'havven',
            'BAL': 'balancer',
            'REN': 'republic-protocol',
            'KNC': 'kyber-network-crystal',
            'ZRX': '0x',
            'MANA': 'decentraland',
            'SAND': 'the-sandbox',
            'AXS': 'axie-infinity',
            'ENJ': 'enjincoin',
            'CHZ': 'chiliz',
            'GALA': 'gala',
            'ROSE': 'oasis-network',
            'ONE': 'harmony',
            'HOT': 'holo',
            'BAT': 'basic-attention-token',
            
            # Layer 1 & 2
            'SUI': 'sui',
            'SEI': 'sei-network',
            'TIA': 'celestia',
            'INJ': 'injective-protocol',
            'KAS': 'kaspa',
            'RUNE': 'thorchain',
            'FLOW': 'flow',
            'EGLD': 'elrond-erd-2',
            'ZIL': 'zilliqa',
            'QTUM': 'qtum',
            'NEO': 'neo',
            'WAVES': 'waves',
            'XTZ': 'tezos',
            'IOTA': 'iota',
            'NANO': 'nano',
            'XEM': 'nem',
            'VTHO': 'vethor-token',
            'ICX': 'icon',
            'ONT': 'ontology',
            'ZEN': 'zencash',
            
            # Exchange Tokens
            'OKB': 'okb',
            'HT': 'huobi-token',
            'GT': 'gatechain-token',
            'KCS': 'kucoin-shares',
            'BTT': 'bittorrent',
            'CRO': 'crypto-com-chain',
            'FTT': 'ftx-token',
            'LEO': 'leo-token',
            'BNT': 'bancor',
            
            # Meme & Social
            'PEPE': 'pepe',
            'FLOKI': 'floki',
            'BONK': 'bonk',
            'WIF': 'dogwifcoin',
            'MYRO': 'myro',
            'POPCAT': 'popcat',
            'BOOK': 'book-of-meme',
            'TURBO': 'turbo',
            'SPX': 'spx6900',
            'BOME': 'book-of-meme',
            
            # AI & Tech
            'FET': 'fetch-ai',
            'OCEAN': 'ocean-protocol',
            'AGIX': 'singularitynet',
            'RNDR': 'render-token',
            'AKT': 'akash-network',
            'HFT': 'hashflow',
            'TAO': 'bittensor',
            'BITTENSOR': 'bittensor',
            
            # Privacy & Security
            'ZEC': 'zcash',
            'DASH': 'dash',
            'XHV': 'haven-protocol',
            'BEAM': 'beam',
            'GRIN': 'grin',
            'PIVX': 'pivx',
            'FIRO': 'firo',
            'XVG': 'verge',
            
            # Oracle & Data
            'BAND': 'band-protocol',
            'API3': 'api3',
            'DIA': 'dia-data',
            'NEST': 'nest',
            'PENDLE': 'pendle',
            'PERP': 'perpetual-protocol',
            'DYDX': 'dydx-chain',
            'GMX': 'gmx',
            
            # Metaverse & NFT
            'APE': 'apecoin',
            'IMX': 'immutable-x',
            
            # Additional Popular Coins
            'CAKE': 'pancakeswap-token',
            'BAKE': 'bakerytoken',
            'SXP': 'swipe',
            'WIN': 'wink',
            'JST': 'just',
            'SUN': 'sun-token',
            'BUSD': 'binance-usd',
            'USDD': 'usdd',
            'TUSD': 'true-usd',
            'FRAX': 'frax',
            'LUSD': 'liquity-usd',
            'GUSD': 'gemini-dollar',
            'PAX': 'paxos-standard',
            'USDP': 'pax-dollar',
            
            # More Altcoins
            'RVN': 'ravencoin',
            'ERG': 'ergo',
            'XDC': 'xdce-crowd-sale',
            '1INCH': '1inch',
        }
        
        return list(symbol_to_id.values())
    
    @staticmethod
    def _coingecko_id_to_symbol(coin_id):
        """Convert CoinGecko coin ID to symbol"""
        # Reverse mapping of coin IDs to symbols
        id_to_symbol = {
            'bitcoin': 'BTC',
            'ethereum': 'ETH',
            'ripple': 'XRP',
            'tether': 'USDT',
            'binancecoin': 'BNB',
            'solana': 'SOL',
            'usd-coin': 'USDC',
            'dogecoin': 'DOGE',
            'tron': 'TRX',
            'cardano': 'ADA',
            'chainlink': 'LINK',
            'stellar': 'XLM',
            'staked-ether': 'STETH',
            'avalanche-2': 'AVAX',
            'polkadot': 'DOT',
            'matic-network': 'MATIC',
            'the-open-network': 'TON',
            'shiba-inu': 'SHIB',
            'dai': 'DAI',
            'uniswap': 'UNI',
            'bitcoin-cash': 'BCH',
            'litecoin': 'LTC',
            'cosmos': 'ATOM',
            'ethereum-classic': 'ETC',
            'filecoin': 'FIL',
            'near': 'NEAR',
            'aptos': 'APT',
            'optimism': 'OP',
            'arbitrum': 'ARB',
            'maker': 'MKR',
            'vechain': 'VET',
            'internet-computer': 'ICP',
            'algorand': 'ALGO',
            'fantom': 'FTM',
            'theta-token': 'THETA',
            'monero': 'XMR',
            'hedera-hashgraph': 'HBAR',
            'immutable-x': 'IMX',
            'blockstack': 'STX',
            'the-graph': 'GRT',
            'aave': 'AAVE',
            'compound-governance-token': 'COMP',
            'curve-dao-token': 'CRV',
            'sushi': 'SUSHI',
            'yearn-finance': 'YFI',
            'havven': 'SNX',
            'balancer': 'BAL',
            'republic-protocol': 'REN',
            'kyber-network-crystal': 'KNC',
            '0x': 'ZRX',
            'decentraland': 'MANA',
            'the-sandbox': 'SAND',
            'axie-infinity': 'AXS',
            'enjincoin': 'ENJ',
            'chiliz': 'CHZ',
            'gala': 'GALA',
            'oasis-network': 'ROSE',
            'harmony': 'ONE',
            'holo': 'HOT',
            'basic-attention-token': 'BAT',
            'sui': 'SUI',
            'sei-network': 'SEI',
            'celestia': 'TIA',
            'injective-protocol': 'INJ',
            'kaspa': 'KAS',
            'thorchain': 'RUNE',
            'flow': 'FLOW',
            'elrond-erd-2': 'EGLD',
            'zilliqa': 'ZIL',
            'qtum': 'QTUM',
            'neo': 'NEO',
            'waves': 'WAVES',
            'tezos': 'XTZ',
            'iota': 'IOTA',
            'nano': 'NANO',
            'nem': 'XEM',
            'vethor-token': 'VTHO',
            'icon': 'ICX',
            'ontology': 'ONT',
            'zencash': 'ZEN',
            'okb': 'OKB',
            'huobi-token': 'HT',
            'gatechain-token': 'GT',
            'kucoin-shares': 'KCS',
            'bittorrent': 'BTT',
            'crypto-com-chain': 'CRO',
            'ftx-token': 'FTT',
            'leo-token': 'LEO',
            'bancor': 'BNT',
            'pepe': 'PEPE',
            'floki': 'FLOKI',
            'bonk': 'BONK',
            'dogwifcoin': 'WIF',
            'myro': 'MYRO',
            'popcat': 'POPCAT',
            'book-of-meme': 'BOME',
            'turbo': 'TURBO',
            'spx6900': 'SPX',
            'fetch-ai': 'FET',
            'ocean-protocol': 'OCEAN',
            'singularitynet': 'AGIX',
            'render-token': 'RNDR',
            'akash-network': 'AKT',
            'hashflow': 'HFT',
            'bittensor': 'TAO',
            'zcash': 'ZEC',
            'dash': 'DASH',
            'haven-protocol': 'XHV',
            'beam': 'BEAM',
            'grin': 'GRIN',
            'pivx': 'PIVX',
            'firo': 'FIRO',
            'verge': 'XVG',
            'band-protocol': 'BAND',
            'api3': 'API3',
            'dia-data': 'DIA',
            'nest': 'NEST',
            'pendle': 'PENDLE',
            'perpetual-protocol': 'PERP',
            'dydx-chain': 'DYDX',
            'gmx': 'GMX',
            'apecoin': 'APE',
            'pancakeswap-token': 'CAKE',
            'bakerytoken': 'BAKE',
            'swipe': 'SXP',
            'wink': 'WIN',
            'just': 'JST',
            'sun-token': 'SUN',
            'binance-usd': 'BUSD',
            'usdd': 'USDD',
            'true-usd': 'TUSD',
            'frax': 'FRAX',
            'liquity-usd': 'LUSD',
            'gemini-dollar': 'GUSD',
            'paxos-standard': 'PAX',
            'pax-dollar': 'USDP',
            'ravencoin': 'RVN',
            'ergo': 'ERG',
            'xdce-crowd-sale': 'XDC',
            '1inch': '1INCH',
        }
        
        return id_to_symbol.get(coin_id, coin_id.upper())


# Global instance
real_price_service = RealPriceService()


def get_live_prices():
    """Get live cryptocurrency prices"""
    return real_price_service.get_live_prices()


def get_symbol_price(symbol):
    """Get price for a specific symbol"""
    return real_price_service.get_symbol_price(symbol)


def refresh_prices():
    """Force refresh of prices"""
    return real_price_service.refresh_prices()
