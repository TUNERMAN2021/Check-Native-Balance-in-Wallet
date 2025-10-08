import requests
import pandas as pd
from web3 import Web3
import time
from itertools import cycle
import random
import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Список RPC-нод для каждой сети
RPC_URLS = {
    'Ethereum': [
        'https://1rpc.io/eth',
        'https://ethereum-rpc.publicnode.com',
        'https://eth.drpc.org'
    ],
    'Optimism': [
        'https://mainnet.optimism.io',
        'https://optimism-rpc.publicnode.com'
    ],
    'Arbitrum': [
        'https://arbitrum-one-rpc.publicnode.com',
        'https://arbitrum.drpc.org'
    ],
    'Base': [
        'https://mainnet.base.org',
        'https://base.drpc.org'
    ],
    'BSC': [
        'https://bsc.drpc.org',
        'https://bsc-rpc.publicnode.com'
    ],
    'Polygon': [
        'https://polygon-rpc.com',
        'https://polygon.drpc.org'
    ]
}

# Чтение адресов кошельков
def load_wallets(file_path='wallet.txt'):
    logger.info(f"Чтение файла кошельков: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            wallets = [line.strip() for line in file if line.strip()]
        logger.info(f"Найдено {len(wallets)} кошельков: {wallets}")
        return wallets
    except FileNotFoundError:
        logger.error(f"Файл {file_path} не найден")
        return []
    except Exception as e:
        logger.error(f"Ошибка при чтении {file_path}: {e}")
        return []

# Чтение прокси
def load_proxies(file_path='proxy.txt'):
    logger.info(f"Чтение файла прокси: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            proxies = [line.strip() for line in file if line.strip()]
        logger.info(f"Найдено {len(proxies)} прокси: {proxies}")
        return proxies
    except FileNotFoundError:
        logger.warning(f"Файл {file_path} не найден, работа без прокси")
        return []
    except Exception as e:
        logger.error(f"Ошибка при чтении {file_path}: {e}")
        return []

# Проверка валидности адреса и преобразование в checksum
def is_valid_address(address):
    try:
        checksum_address = Web3.to_checksum_address(address)
        logger.info(f"Проверка адреса {address}: валиден (преобразован в {checksum_address})")
        return checksum_address
    except Exception as e:
        logger.error(f"Проверка адреса {address}: невалиден ({e})")
        return None

# Подключение к RPC
def connect_to_rpc(network, proxy=None):
    logger.info(f"Подключение к сети {network} с прокси {proxy}")
    for rpc_url in RPC_URLS[network]:
        logger.info(f"Попытка подключения к {rpc_url}")
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'proxies': {'http': proxy, 'https': proxy} if proxy else None}))
            if w3.is_connected():
                logger.info(f"Успешно подключено к {rpc_url}")
                return w3, rpc_url
            else:
                logger.warning(f"Не удалось подключиться к {rpc_url}: нет соединения")
        except Exception as e:
            logger.error(f"Ошибка подключения к {rpc_url}: {e}")
    logger.error(f"Не удалось подключиться к сети {network} через все RPC")
    return None, None

# Получение баланса
def get_balance(w3, address, network):
    logger.info(f"Получение баланса для {address} в сети {network}")
    try:
        if network in ['Ethereum', 'Optimism', 'Arbitrum', 'Base']:
            balance = w3.eth.get_balance(address)
            balance_eth = w3.from_wei(balance, 'ether')
            logger.info(f"Баланс {address} в {network}: {balance_eth} ETH")
            return balance_eth
        elif network == 'BSC':
            balance = w3.eth.get_balance(address)
            balance_bnb = w3.from_wei(balance, 'ether')
            logger.info(f"Баланс {address} в BSC: {balance_bnb} BNB")
            return balance_bnb
        elif network == 'Polygon':
            balance = w3.eth.get_balance(address)
            balance_pol = w3.from_wei(balance, 'ether')
            logger.info(f"Баланс {address} в Polygon: {balance_pol} POL")
            return balance_pol
    except Exception as e:
        logger.error(f"Ошибка получения баланса для {address} в сети {network}: {e}")
        return None

# Проверка балансов
def check_balances(wallets, proxies):
    logger.info("Начало проверки балансов")
    results = {wallet: {'ETH mainnet': 0, 'ETH op': 0, 'ETH arb': 0, 'ETH base': 0, 'BNB': 0, 'Pol': 0} for wallet in wallets}
    proxy_cycle = cycle(proxies) if proxies else cycle([None])
    current_proxy = next(proxy_cycle)

    for wallet in wallets:
        checksum_address = is_valid_address(wallet)
        if not checksum_address:
            continue

        for network, column in [
            ('Ethereum', 'ETH mainnet'),
            ('Optimism', 'ETH op'),
            ('Arbitrum', 'ETH arb'),
            ('Base', 'ETH base'),
            ('BSC', 'BNB'),
            ('Polygon', 'Pol')
        ]:
            attempts = 0
            max_attempts = len(RPC_URLS[network]) * (len(proxies) if proxies else 1)
            while attempts < max_attempts:
                w3, rpc_url = connect_to_rpc(network, current_proxy)
                if w3:
                    balance = get_balance(w3, checksum_address, network)
                    if balance is not None:
                        results[wallet][column] = float(balance)  # Преобразуем в float для Excel
                        break
                    else:
                        logger.warning(f"Смена RPC для {network} (попытка {attempts + 1}/{max_attempts})")
                        RPC_URLS[network].append(RPC_URLS[network].pop(0))  # Смена RPC
                else:
                    logger.warning(f"Смена прокси для {network} (попытка {attempts + 1}/{max_attempts})")
                    current_proxy = next(proxy_cycle)  # Смена прокси
                attempts += 1
                time.sleep(random.uniform(0.5, 2))  # Задержка

    logger.info(f"Результаты проверки балансов: {results}")
    return results

# Сохранение в Excel
def save_to_excel(results, output_file='balances.xlsx'):
    logger.info(f"Сохранение результатов в {output_file}")
    try:
        df = pd.DataFrame.from_dict(results, orient='index')
        df.index.name = 'Wallet Address'
        df.to_excel(output_file, engine='openpyxl')
        logger.info(f"Результаты успешно сохранены в {output_file}")
        logger.info(f"Содержимое таблицы:\n{df}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в {output_file}: {e}")

# Основной запуск
def main():
    logger.info("Запуск скрипта")
    wallets = load_wallets()
    proxies = load_proxies()

    if not wallets:
        logger.error("Нет валидных адресов кошельков, завершение работы")
        return

    results = check_balances(wallets, proxies)
    save_to_excel(results)
    logger.info("Скрипт завершил работу")

if __name__ == "__main__":
    main()
