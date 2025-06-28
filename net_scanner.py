import ipaddress
import subprocess
import sys
import re
from scapy.all import ARP, Ether, srp

def get_lan_info_macos():
    """
    Находит параметры физической локальной сети (Wi-Fi/Ethernet),
    целенаправленно игнорируя VPN-интерфейсы.
    """
    try:
        # 1. Получаем полную таблицу маршрутизации для IPv4
        netstat_output = subprocess.check_output(["netstat", "-nr", "-f", "inet"], text=True)
        
        # 2. Ищем строку, которая определяет шлюз для физического интерфейса (enX)
        #    Это строка вида "default <gateway_ip> ... <interface>"
        lan_gateway_match = re.search(r"^default\s+([\d\.]+)\s+.*? (en\d+)", netstat_output, re.MULTILINE)
        
        if not lan_gateway_match:
            print("Не удалось найти шлюз для физического интерфейса (enX) в таблице маршрутизации.")
            return None, None, None
            
        gateway_ip = lan_gateway_match.group(1)
        net_interface = lan_gateway_match.group(2)

        # 3. Получаем IP-адрес хоста для этого конкретного интерфейса
        ifconfig_output = subprocess.check_output(["ifconfig", net_interface], text=True)
        host_ip_match = re.search(r"inet ([\d\.]+) netmask", ifconfig_output)
        
        if not host_ip_match:
            print(f"Не удалось найти IPv4-адрес для интерфейса {net_interface}.")
            return None, None, None
            
        host_ip = host_ip_match.group(1)
        
        return host_ip, gateway_ip, net_interface

    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения системной команды: {e}")
        return None, None, None
    except Exception as e:
        print(f"Непредвиденная ошибка при определении сети: {e}")
        return None, None, None

def scan_network(ip_range, interface):
    """Сканирует сеть с помощью ARP-запросов."""
    print(f"Используетс\u044f интерфейс: {interface}")
    arp_request = ARP(pdst=ip_range)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered_list = srp(arp_request_broadcast, timeout=3, iface=interface, verbose=False)[0]

    devices = []
    for sent, received in answered_list:
        devices.append(received.psrc)
    return devices

if __name__ == "__main__":
    if sys.platform == "darwin" and not __import__('os').geteuid() == 0:
        print("Ошибка: для корректной работы на macOS скрипт необходимо запустить с правами sudo.")
        sys.exit(1)

    host_ip, gateway_ip, net_interface = get_lan_info_macos()

    if not all((host_ip, gateway_ip, net_interface)):
        print("Не удалось определить параметры локальной сети.")
        print("Пожалуйста, убедитесь, что вы подключены к Wi-Fi/Ethernet.")
        sys.exit(1)

    print(f"IP-адрес хоста: {host_ip}")
    print(f"IP-адрес шлюза: {gateway_ip}")

    try:
        # Сканируем подсеть, определенную шлюзом
        network = ipaddress.ip_network(f"{gateway_ip}/24", strict=False)
        ip_range_to_scan = str(network)
        print(f"Сканирование подсети: {ip_range_to_scan}")

        print("Сканирование сети...")
        active_devices = scan_network(ip_range_to_scan, net_interface)

        # Добавляем IP хоста и шлюза в список
        if host_ip not in active_devices:
            active_devices.append(host_ip)
        if gateway_ip not in active_devices:
            active_devices.append(gateway_ip)

        # Убираем дубликаты и сортируем
        unique_devices = sorted(list(set(active_devices)), key=ipaddress.ip_address)

        print("\n--- Обнаруженные IP-адреса ---")
        for ip in unique_devices:
            print(ip)
        print("-----------------------------")

    except Exception as e:
        print(f"\nПроизошла непредвиденная ошибка при сканировании: {e}")



