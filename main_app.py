import pygame
import math
import ipaddress
import subprocess
import sys
import re
from scapy.all import ARP, Ether, srp

# --- Параметры визуализации ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
BACKGROUND_COLOR = (20, 30, 40)
NODE_COLOR = (70, 170, 210)
ROUTER_COLOR = (255, 100, 100)
LINE_COLOR = (100, 100, 100)
TEXT_COLOR = (230, 230, 230)
NODE_RADIUS = 30
FONT_SIZE = 16

# --- Функции сканирования (из net_scanner.py) ---
def get_lan_info_macos():
    """
    Находит параметры физической локальной сети (Wi-Fi/Ethernet),
    целенаправленно игнорируя VPN-интерфейсы.
    """
    try:
        netstat_output = subprocess.check_output(["netstat", "-nr", "-f", "inet"], text=True)
        lan_gateway_match = re.search(r"^default\s+([\d\.]+)\s+.*? (en\d+)", netstat_output, re.MULTILINE)
        
        if not lan_gateway_match:
            return None, None, None
            
        gateway_ip = lan_gateway_match.group(1)
        net_interface = lan_gateway_match.group(2)

        ifconfig_output = subprocess.check_output(["ifconfig", net_interface], text=True)
        host_ip_match = re.search(r"inet ([\d\.]+) netmask", ifconfig_output)
        
        if not host_ip_match:
            return None, None, None
            
        host_ip = host_ip_match.group(1)
        return host_ip, gateway_ip, net_interface

    except Exception:
        return None, None, None

def scan_network(ip_range, interface):
    """Сканирует сеть с помощью ARP-запросов."""
    print(f"Используется интерфейс: {interface}")
    arp_request = ARP(pdst=ip_range)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered_list = srp(arp_request_broadcast, timeout=3, iface=interface, verbose=False)[0]
    devices = [received.psrc for _, received in answered_list]
    return devices

# --- Основная функция ---
def main():
    # --- Этап 1: Сканирование сети ---
    print("Запуск сканирования сети...")
    if sys.platform == "darwin" and not __import__('os').geteuid() == 0:
        print("Ошибка: для сканирования сети скрипт необходимо запустить с правами sudo.")
        sys.exit(1)

    host_ip, gateway_ip, net_interface = get_lan_info_macos()

    if not all((host_ip, gateway_ip, net_interface)):
        print("Не удалось определить параметры локальной сети. Завершение работы.")
        sys.exit(1)
    
    print(f"Хост: {host_ip}, Шлюз: {gateway_ip}, Интерфейс: {net_interface}")
    
    try:
        network = ipaddress.ip_network(f"{gateway_ip}/24", strict=False)
        ip_range_to_scan = str(network)
        print(f"Сканирование подсети: {ip_range_to_scan}...")
        
        active_devices = scan_network(ip_range_to_scan, net_interface)
        
        if host_ip not in active_devices:
            active_devices.append(host_ip)
        if gateway_ip not in active_devices:
            active_devices.append(gateway_ip)
            
        ip_addresses = sorted(list(set(active_devices)), key=ipaddress.ip_address)
        print(f"Обнаружены устройства: {ip_addresses}")

    except Exception as e:
        print(f"Ошибка при сканировании: {e}")
        # В случае ошибки используем данные по умолчанию для демонстрации
        ip_addresses = [host_ip, gateway_ip]
        print(f"Используются данные по умолчанию: {ip_addresses}")

    # --- Этап 2: Визуализация ---
    print("Запуск визуализации...")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Сетевой Визуализатор")
    font = pygame.font.SysFont(None, FONT_SIZE)

    nodes = {}
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    client_ips = [ip for ip in ip_addresses if ip != gateway_ip]
    
    nodes[gateway_ip] = (center_x, center_y)
    
    num_clients = len(client_ips)
    radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 3
    angle_step = 2 * math.pi / num_clients if num_clients > 0 else 0

    for i, ip in enumerate(client_ips):
        angle = i * math.pi / (num_clients / 2) if num_clients > 1 else 0
        x = center_x + int(radius * math.cos(angle))
        y = center_y + int(radius * math.sin(angle))
        nodes[ip] = (x, y)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(BACKGROUND_COLOR)

        router_pos = nodes.get(gateway_ip)
        if router_pos:
            for ip, pos in nodes.items():
                if ip != gateway_ip:
                    pygame.draw.line(screen, LINE_COLOR, router_pos, pos, 2)

        for ip, pos in nodes.items():
            color = ROUTER_COLOR if ip == gateway_ip else NODE_COLOR
            pygame.draw.circle(screen, color, pos, NODE_RADIUS)
            text_surface = font.render(ip, True, TEXT_COLOR)
            text_rect = text_surface.get_rect(center=(pos[0], pos[1] + NODE_RADIUS + 10))
            screen.blit(text_surface, text_rect)

        pygame.display.flip()

    pygame.quit()
    print("Визуализатор закрыт.")

if __name__ == '__main__':
    main()
