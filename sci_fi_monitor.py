import pygame
import math
import ipaddress
import subprocess
import sys
import re
import random
import threading
import time
from scapy.all import ARP, Ether, srp
import os

# --- Параметры визуализации ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 800
BACKGROUND_COLOR = (0, 10, 25)
LINE_COLOR = (0, 100, 150)
TEXT_COLOR = (200, 255, 255)
INFO_TEXT_COLOR = (255, 255, 255)
INFO_BG_COLOR = (10, 30, 50, 220)
BUTTON_COLOR = (0, 150, 255)
BUTTON_HOVER_COLOR = (100, 200, 255)

NODE_COLORS = {"router": (255, 0, 100), "host": (0, 255, 255), "device": (0, 150, 255)}
GLOW_COLORS = {"router": (100, 0, 50), "host": (0, 100, 100), "device": (0, 50, 100)}
PING_FLASH_COLORS = {"success": (0, 255, 0), "fail": (255, 0, 0)}

NODE_RADIUS = 30
FONT_NAME = "Orbitron-Regular.ttf"
FONT_SIZE = 14
INFO_FONT_SIZE = 16
TITLE_FONT_SIZE = 24

# --- Глобальные переменные состояния ---
ping_results = {}  # {ip: {"status": "success/fail", "timestamp": time.time()}}

# --- Функции сканирования ---
def get_lan_info_macos():
    try:
        netstat_output = subprocess.check_output(["netstat", "-nr", "-f", "inet"], text=True)
        lan_gateway_match = re.search(r"^default\s+([\d\.]+)\s+.*? (en\d+)", netstat_output, re.MULTILINE)
        if not lan_gateway_match: return None, None, None
        gateway_ip, net_interface = lan_gateway_match.groups()
        ifconfig_output = subprocess.check_output(["ifconfig", net_interface], text=True)
        host_ip_match = re.search(r"inet ([\d\.]+) netmask", ifconfig_output)
        if not host_ip_match: return None, None, None
        host_ip = host_ip_match.group(1)
        return host_ip, gateway_ip, net_interface
    except Exception: return None, None, None

def scan_network_with_mac(ip_range, interface):
    print(f"Сканирование {ip_range} через {interface}...")
    arp_request = ARP(pdst=ip_range)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered_list = srp(arp_request_broadcast, timeout=4, iface=interface, verbose=False)[0]
    return [{'ip': r.psrc, 'mac': r.hwsrc} for _, r in answered_list]

def run_ping(ip):
    """Запускает ping в отдельном потоке."""
    try:
        # -c 1: 1 пакет, -W 1000: таймаут 1000 мс
        command = ["ping", "-c", "1", "-W", "1000", ip]
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        status = "success" if result.returncode == 0 else "fail"
    except subprocess.TimeoutExpired:
        status = "fail"
    ping_results[ip] = {"status": status, "timestamp": time.time()}

# --- Классы для анимации ---
class Packet:
    def __init__(self, start_pos, end_pos):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.progress = 0.0
        self.speed = 0.02
        self.color = (255, 255, 0)
        self.size = 3

    def move(self):
        self.progress += self.speed
        if self.progress > 1.0:
            return False
        return True

    def draw(self, screen):
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * self.progress
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * self.progress
        pygame.draw.circle(screen, self.color, (int(x), int(y)), self.size)

# --- Основная функция ---
def main():
    # --- Этап 1: Сканирование ---
    print("Запуск ск��нирования сети...")
    if sys.platform == "darwin" and not __import__('os').geteuid() == 0:
        print("Ошибка: Требуются права sudo. Запустите: sudo python3 sci_fi_monitor.py")
        sys.exit(1)

    host_ip, gateway_ip, net_interface = get_lan_info_macos()
    if not all((host_ip, gateway_ip, net_interface)):
        print("Не удалось определить параметры локальной сети."); sys.exit(1)

    try:
        network = ipaddress.ip_network(f"{gateway_ip}/24", strict=False)
        devices_found = scan_network_with_mac(str(network), net_interface)
        found_ips = [dev['ip'] for dev in devices_found]
        if host_ip not in found_ips: devices_found.append({'ip': host_ip, 'mac': 'N/A (Host)'})
        if gateway_ip not in found_ips: devices_found.append({'ip': gateway_ip, 'mac': 'N/A (Gateway)'})
    except Exception as e:
        print(f"Ошибка сканирования: {e}. Используются данные по умолчанию.")
        devices_found = [{'ip': host_ip, 'mac': 'N/A (Host)'}, {'ip': gateway_ip, 'mac': 'N/A (Gateway)'}]
    
    print(f"Обнаружено {len(devices_found)} устройств.")

    # --- Этап 2: Визуализация ---
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Sci-Fi Network Monitor v2.0")
    
    font_path = FONT_NAME if os.path.exists(FONT_NAME) else None
    font = pygame.font.Font(font_path, FONT_SIZE)
    info_font = pygame.font.Font(font_path, INFO_FONT_SIZE)
    title_font = pygame.font.Font(font_path, TITLE_FONT_SIZE)
    if not os.path.exists(FONT_NAME): print(f"Шрифт '{FONT_NAME}' не найден.")

    nodes = {}
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    client_devices = [dev for dev in devices_found if dev['ip'] != gateway_ip]
    
    nodes[gateway_ip] = {'pos': (center_x, center_y), 'type': 'router', 'mac': 'N/A'}
    
    num_clients = len(client_devices)
    radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 3
    angle_step = 2 * math.pi / num_clients if num_clients > 0 else 0

    for i, device in enumerate(client_devices):
        angle = i * angle_step
        x = center_x + int(radius * math.cos(angle))
        y = center_y + int(radius * math.sin(angle))
        node_type = 'host' if device['ip'] == host_ip else 'device'
        nodes[device['ip']] = {'pos': (x, y), 'type': node_type, 'mac': device['mac']}

    packets = []
    selected_ip = None
    clock = pygame.time.Clock()
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # ЛКМ
                    clicked_on_node = False
                    for ip, data in nodes.items():
                        if math.hypot(mouse_pos[0] - data['pos'][0], mouse_pos[1] - data['pos'][1]) < NODE_RADIUS:
                            selected_ip = ip
                            clicked_on_node = True
                            break
                    if not clicked_on_node:
                        # Проверяем клик по кнопке Ping
                        if selected_ip and info_panel_rect and ping_button_rect.collidepoint(mouse_pos):
                            print(f"Запрос ping для {selected_ip}...")
                            threading.Thread(target=run_ping, args=(selected_ip,)).start()
                        else:
                            selected_ip = None # Сброс выделения

        screen.fill(BACKGROUND_COLOR)
        
        if random.randint(0, 20) == 0 and len(nodes) > 1:
            sender_ip = random.choice(list(nodes.keys()))
            receiver_ip = gateway_ip if sender_ip != gateway_ip else random.choice(client_devices)['ip']
            if receiver_ip in nodes:
                packets.append(Packet(nodes[sender_ip]['pos'], nodes[receiver_ip]['pos']))

        for p in packets[:]:
            if not p.move(): packets.remove(p)
            else: p.draw(screen)

        pulse = (math.sin(pygame.time.get_ticks() * 0.002) + 1) / 2
        
        router_node = nodes.get(gateway_ip)
        if router_node:
            for ip, data in nodes.items():
                if ip != gateway_ip: pygame.draw.line(screen, LINE_COLOR, router_node['pos'], data['pos'], 1)

        for ip, data in nodes.items():
            pos, node_type = data['pos'], data['type']
            
            # Вспышка от пинга
            if ip in ping_results:
                result = ping_results[ip]
                if time.time() - result["timestamp"] < 0.5: # Длительность вспышки
                    flash_alpha = 255 * (1 - (time.time() - result["timestamp"]) / 0.5)
                    flash_color = PING_FLASH_COLORS[result["status"]] + (int(flash_alpha),)
                    s = pygame.Surface((NODE_RADIUS*4, NODE_RADIUS*4), pygame.SRCALPHA)
                    pygame.draw.circle(s, flash_color, (NODE_RADIUS*2, NODE_RADIUS*2), NODE_RADIUS*2)
                    screen.blit(s, (pos[0] - NODE_RADIUS*2, pos[1] - NODE_RADIUS*2))
                else:
                    del ping_results[ip]

            # Выделение выбранного узла
            if ip == selected_ip:
                pygame.draw.circle(screen, (255, 255, 0), pos, NODE_RADIUS + 8, 2)

            glow_radius = int(NODE_RADIUS * 1.5 + pulse * 5)
            glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, GLOW_COLORS[node_type] + (80,), (glow_radius, glow_radius), glow_radius)
            screen.blit(glow_surface, (pos[0] - glow_radius, pos[1] - glow_radius))

            pygame.draw.circle(screen, NODE_COLORS[node_type], pos, NODE_RADIUS)
            
            text_surface = font.render(ip, True, TEXT_COLOR)
            text_rect = text_surface.get_rect(center=(pos[0], pos[1] + NODE_RADIUS + 15))
            screen.blit(text_surface, text_rect)

        info_panel_rect = None
        if selected_ip:
            data = nodes[selected_ip]
            info_text = [f"IP: {selected_ip}", f"MAC: {data['mac']}", f"Type: {data['type'].capitalize()}"]
            panel_w, panel_h = 300, 140
            info_panel_rect = pygame.Rect(SCREEN_WIDTH - panel_w - 20, 20, panel_w, panel_h)
            
            s = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            s.fill(INFO_BG_COLOR)
            screen.blit(s, info_panel_rect.topleft)
            
            title_surf = title_font.render("DEVICE INFO", True, TEXT_COLOR)
            screen.blit(title_surf, (info_panel_rect.x + 20, info_panel_rect.y + 15))

            for i, line in enumerate(info_text):
                info_surface = info_font.render(line, True, INFO_TEXT_COLOR)
                screen.blit(info_surface, (info_panel_rect.x + 20, info_panel_rect.y + 50 + i * 22))
            
            ping_button_rect = pygame.Rect(info_panel_rect.x + 20, info_panel_rect.y + 105, panel_w - 40, 25)
            button_c = BUTTON_HOVER_COLOR if ping_button_rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(screen, button_c, ping_button_rect, border_radius=5)
            ping_text_surf = info_font.render("Ping Device", True, (0,0,0))
            screen.blit(ping_text_surf, ping_text_surf.get_rect(center=ping_button_rect.center))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == '__main__':
    main()