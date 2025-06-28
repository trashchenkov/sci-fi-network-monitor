import pygame
import math

# --- Параметры ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
BACKGROUND_COLOR = (20, 30, 40)
NODE_COLOR = (70, 170, 210)
ROUTER_COLOR = (255, 100, 100)
LINE_COLOR = (100, 100, 100)
TEXT_COLOR = (230, 230, 230)
NODE_RADIUS = 30
FONT_SIZE = 16

# --- Данные (полученные на предыдущем шаге) ---
IP_ADDRESSES = ["192.168.1.1", "192.168.1.102"]
GATEWAY_IP = "192.168.1.1"

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Сетевой Визуализатор")
    font = pygame.font.SysFont(None, FONT_SIZE)

    # --- Расчет позиций узлов ---
    nodes = {}
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    
    # Разделяем роутер и остальные устройства
    client_ips = [ip for ip in IP_ADDRESSES if ip != GATEWAY_IP]
    
    # Позиция роутера
    nodes[GATEWAY_IP] = (center_x, center_y)
    
    # Позиции остальных ��стройств по кругу
    num_clients = len(client_ips)
    radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) / 3
    angle_step = 2 * math.pi / num_clients if num_clients > 0 else 0

    for i, ip in enumerate(client_ips):
        angle = i * angle_step
        x = center_x + int(radius * math.cos(angle))
        y = center_y + int(radius * math.sin(angle))
        nodes[ip] = (x, y)

    # --- Главный цикл ---
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # --- Отрисовка ---
        screen.fill(BACKGROUND_COLOR)

        # 1. Отрисовка линий
        router_pos = nodes.get(GATEWAY_IP)
        if router_pos:
            for ip, pos in nodes.items():
                if ip != GATEWAY_IP:
                    pygame.draw.line(screen, LINE_COLOR, router_pos, pos, 2)

        # 2. Отрисовка узлов и текста
        for ip, pos in nodes.items():
            color = ROUTER_COLOR if ip == GATEWAY_IP else NODE_COLOR
            pygame.draw.circle(screen, color, pos, NODE_RADIUS)
            
            # Подпись IP-адреса
            text_surface = font.render(ip, True, TEXT_COLOR)
            text_rect = text_surface.get_rect(center=(pos[0], pos[1] + NODE_RADIUS + 10))
            screen.blit(text_surface, text_rect)

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
