%% DEMO_CINEMATICA_Y_PROYECCIONES — Mini-Pro 4-DOF B2 (Peter Corke RTB10)
% =========================================================================
% Script principal de la Iteración 1 para la materia de Robótica:
%   1. Construye el robot 4R exacto al milímetro con el CAD (`cad/params.py`).
%   2. Valida Cinemática Directa (`fkine`) e Inversa Analítica (`ikine_minipro_4dof`).
%   3. Calcula y grafica el Espacio de Trabajo (Workspace) 3D y proyecciones XY / XZ / YZ.
%   4. Simula una trayectoria articular suave (`jtraj`) Pick-and-Place con pinza horizontal (phi=0°),
%      graficando posición q(t), velocidad q̇(t) y aceleración q̈(t).
%   5. Simula una trayectoria cartesiana en línea recta 3D sobre el escritorio (pinza hacia abajo),
%      mostrando proyecciones ortogonales XY/XZ/YZ y el perfil de manipulabilidad (Jacobiano).
%
% Exporta automáticamente todas las figuras en alta resolución en `docs/graficas_matlab/`.

clear; clc; close all;

%% 0. Inicializar robot y carpeta de exportación
[robot, P] = robot_minipro_4dof();

scriptDir = fileparts(mfilename('fullpath'));
outDir = fullfile(fileparts(scriptDir), 'docs', 'graficas_matlab');
if ~exist(outDir, 'dir'), mkdir(outDir); end

disp('=====================================================================');
disp('  MODELO DENAVIT-HARTENBERG — BRAZO MINI-PRO 4-DOF ESTILO B2 (mm)');
disp('=====================================================================');
disp(robot);

%% 1. Validación numérica FK vs IK en Pose Héroe
T_hero = robot.fkine(P.q_hero);
p_hero = transl(T_hero);
[q_check, ok_ik, msg_ik] = ikine_minipro_4dof(p_hero(1), p_hero(2), p_hero(3), 0.0, true, P);
err_deg = max(abs(rad2deg(P.q_hero - q_check)));

fprintf('Pose Héroe CAD : q = [%.1f, %.1f, %.1f, %.1f] deg\n', rad2deg(P.q_hero));
fprintf('TCP fkine (mm) : X = %.2f, Y = %.2f, Z = %.2f mm\n', p_hero(1), p_hero(2), p_hero(3));
fprintf('Validación IK  : %s | Error máx = %.2e deg\n\n', msg_ik, err_deg);

%% FIGURA 1 — Modelo 3D Peter Corke en Pose Héroe
fig1 = figure('Name', 'Fig 1 - Modelo 3D Peter Corke', 'Color', 'w', 'Position', [80 80 880 650]);
ws_box = [-120 260 -240 240 0 330];
robot.plot(P.q_hero, 'workspace', ws_box, 'floorlevel', 0, ...
    'tilesize', 40, 'jointdiam', 1.4, 'scale', 0.65, 'view', [38 24]);
hold on;
% Dibujar círculo de la base Ø 94 mm sobre el escritorio Z=0
th = linspace(0, 2*pi, 80);
plot3((P.base_dia/2)*cos(th), (P.base_dia/2)*sin(th), zeros(size(th)), 'k-', 'LineWidth', 2.2);
plot3(p_hero(1), p_hero(2), p_hero(3), 'ro', 'MarkerSize', 9, 'MarkerFaceColor', [0.85 0.30 0.10]);
title(sprintf('Mini-Pro 4-DOF B2 — Pose Héroe (TCP = [%.1f, %.1f, %.1f] mm, \\phi = 0°)', ...
    p_hero(1), p_hero(2), p_hero(3)), 'FontSize', 12, 'FontWeight', 'bold');
xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
grid on;
exportgraphics(fig1, fullfile(outDir, 'fig1_modelo_3d_hero.png'), 'Resolution', 220);

%% FIGURA 2 — Espacio de Trabajo (Workspace) 3D + Proyecciones XY, XZ, YZ
rng(42);
N_ws = 22000;
Q_rand = zeros(N_ws, 4);
for j = 1:4
    Q_rand(:, j) = P.qlim(j,1) + (P.qlim(j,2) - P.qlim(j,1)) * rand(N_ws, 1);
end

% Cinemática directa vectorizada (idéntica a robot.fkine) para muestreo ultrarrápido
q1 = Q_rand(:,1); q2 = Q_rand(:,2); q3 = Q_rand(:,3); q4 = Q_rand(:,4);
r_ws = P.a2*cos(q2) + P.a3*cos(q2+q3) + P.a4*cos(q2+q3+q4);
X_ws = r_ws .* cos(q1);
Y_ws = r_ws .* sin(q1);
Z_ws = P.d1 + P.a2*sin(q2) + P.a3*sin(q2+q3) + P.a4*sin(q2+q3+q4);

% Filtrar puntos físicamente válidos sobre el escritorio (Z >= 12 mm)
valid = Z_ws >= 12.0;
X_ws = X_ws(valid); Y_ws = Y_ws(valid); Z_ws = Z_ws(valid);

fig2 = figure('Name', 'Fig 2 - Workspace y Proyecciones XY XZ YZ', 'Color', 'w', 'Position', [100 60 1160 820]);
tiledlayout(2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

% 2A: Vista 3D
nexttile;
scatter3(X_ws(1:3:end), Y_ws(1:3:end), Z_ws(1:3:end), 5, Z_ws(1:3:end), 'filled', 'MarkerFaceAlpha', 0.35);
hold on;
plot3((P.base_dia/2)*cos(th), (P.base_dia/2)*sin(th), zeros(size(th)), 'k-', 'LineWidth', 2);
colormap(turbo); cb = colorbar; cb.Label.String = 'Altura Z (mm)';
xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
title('Espacio de Trabajo 3D (Z \ge 12 mm)');
axis equal; grid on; view(38, 26);

% 2B: Proyección XY (Vista Superior)
nexttile;
scatter(X_ws, Y_ws, 4, Z_ws, 'filled', 'MarkerFaceAlpha', 0.25);
hold on;
plot((P.base_dia/2)*cos(th), (P.base_dia/2)*sin(th), 'k-', 'LineWidth', 2);
R_max = P.a2 + P.a3 + P.a4;
th_semi = linspace(-pi/2, pi/2, 120);
plot(R_max*cos(th_semi), R_max*sin(th_semi), 'r--', 'LineWidth', 1.4);
xlabel('X (mm)'); ylabel('Y (mm)');
title(sprintf('Proyección Plano XY (Alcance máx R = %.0f mm)', R_max));
axis equal; grid on;

% 2C: Proyección XZ (Vista Perfil Lateral)
nexttile;
scatter(X_ws, Z_ws, 4, Z_ws, 'filled', 'MarkerFaceAlpha', 0.25);
hold on;
yline(0, 'k-', 'LineWidth', 2);
rectangle('Position', [-P.base_dia/2, 0, P.base_dia, 64], 'FaceColor', [0.15 0.15 0.16], 'EdgeColor', 'k');
xlabel('X (mm)'); ylabel('Z (mm)');
title('Proyección Plano XZ (Perfil Lateral)');
axis equal; grid on; ylim([-10 340]);

% 2D: Proyección YZ (Vista Frontal)
nexttile;
scatter(Y_ws, Z_ws, 4, Z_ws, 'filled', 'MarkerFaceAlpha', 0.25);
hold on;
yline(0, 'k-', 'LineWidth', 2);
rectangle('Position', [-P.base_dia/2, 0, P.base_dia, 64], 'FaceColor', [0.15 0.15 0.16], 'EdgeColor', 'k');
xlabel('Y (mm)'); ylabel('Z (mm)');
title('Proyección Plano YZ (Vista Frontal)');
axis equal; grid on; ylim([-10 340]);

sgtitle('Mini-Pro 4-DOF B2 — Espacio de Trabajo y Proyecciones Ortogonales', 'FontSize', 14, 'FontWeight', 'bold');
exportgraphics(fig2, fullfile(outDir, 'fig2_workspace_proyecciones.png'), 'Resolution', 220);

%% FIGURA 3 — Trayectoria Articular Suave (jtraj) Pick-and-Place Horizontal (phi = 0°)
% Puntos cartesianos (X, Y, Z, phi_deg): tomar pieza a la izquierda, elevar, llevar a la derecha
waypoints = [
    155, -75,  75,  0;   % W1: Recoger objeto (pinza horizontal)
    165,   0, 145,  0;   % W2: Elevación central segura
    155,  75,  75,  0;   % W3: Depositar objeto al lado derecho
];

Q_wp = zeros(size(waypoints, 1), 4);
for k = 1:size(waypoints, 1)
    [Q_wp(k,:), ok_w, msg_w] = ikine_minipro_4dof(waypoints(k,1), waypoints(k,2), waypoints(k,3), waypoints(k,4), true, P);
    assert(ok_w, 'Waypoint %d inválido: %s', k, msg_w);
end

N_seg = 60;
dt = 0.04; % 25 Hz -> 2.4 s por segmento
[q_s1, qd_s1, qdd_s1] = jtraj(Q_wp(1,:), Q_wp(2,:), N_seg);
[q_s2, qd_s2, qdd_s2] = jtraj(Q_wp(2,:), Q_wp(3,:), N_seg);

Q_tr   = [q_s1; q_s2(2:end, :)];
Qd_tr  = [qd_s1; qd_s2(2:end, :)] / dt;
Qdd_tr = [qdd_s1; qdd_s2(2:end, :)] / (dt^2);
t_vec  = (0:size(Q_tr,1)-1)' * dt;

fig3 = figure('Name', 'Fig 3 - Trayectoria Articular jtraj', 'Color', 'w', 'Position', [120 70 1050 760]);
tiledlayout(3, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
cols = [0.12 0.12 0.15; 0.85 0.30 0.10; 0.15 0.45 0.78; 0.20 0.62 0.38];
jnames = {'q_1 (Base)', 'q_2 (Hombro)', 'q_3 (Codo)', 'q_4 (Muñeca)'};

nexttile; hold on; grid on;
for j = 1:4, plot(t_vec, rad2deg(Q_tr(:,j)), 'LineWidth', 2.0, 'Color', cols(j,:)); end
ylabel('Ángulo (°)'); title('Posición Articular q(t) — Polinomio Quíntico jtraj');
legend(jnames, 'Location', 'eastoutside');

nexttile; hold on; grid on;
for j = 1:4, plot(t_vec, rad2deg(Qd_tr(:,j)), 'LineWidth', 1.8, 'Color', cols(j,:)); end
ylabel('Velocidad (°/s)'); title('Velocidad Articular q̇(t) (Arranque y Frenado Suaves en 0)');

nexttile; hold on; grid on;
for j = 1:4, plot(t_vec, rad2deg(Qdd_tr(:,j)), 'LineWidth', 1.8, 'Color', cols(j,:)); end
ylabel('Aceleración (°/s²)'); xlabel('Tiempo (s)');
title('Aceleración Articular q̈(t) (Perfil Continuo sin Golpes)');

sgtitle('Trayectoria Pick-and-Place (jtraj) — Pinza Horizontal \phi = 0°', 'FontSize', 14, 'FontWeight', 'bold');
exportgraphics(fig3, fullfile(outDir, 'fig3_trayectoria_jtraj.png'), 'Resolution', 220);

%% FIGURA 4 — Trayectoria Cartesiana en Línea Recta 3D (Ruta Rectangular) + Proyecciones + Manipulabilidad
% Dibuja un rectángulo preciso sobre el escritorio a Z = 65 mm con pinza inclinada phi = -65°
rect_pts = [
    125, -55, 65;
    175, -55, 65;
    175,  55, 65;
    125,  55, 65;
    125, -55, 65;
];
phi_rect = -65.0;
N_side = 35;

Q_cart = [];
P_cart = [];
M_idx  = [];

for s = 1:size(rect_pts, 1)-1
    pA = rect_pts(s, :);
    pB = rect_pts(s+1, :);
    % Perfil quíntico escalar s(u) in [0, 1] equivalente a ctraj en posición
    u = linspace(0, 1, N_side)';
    if s > 1, u = u(2:end); end
    su = 10*u.^3 - 15*u.^4 + 6*u.^5;
    for k = 1:length(su)
        pt = pA + su(k) * (pB - pA);
        [qk, ok_c, msg_c] = ikine_minipro_4dof(pt(1), pt(2), pt(3), phi_rect, true, P);
        assert(ok_c, 'Punto cartesiano inválido: %s', msg_c);
        Q_cart(end+1, :) = qk; %#ok<SAGROW>
        Tk = robot.fkine(qk);
        P_cart(end+1, :) = transl(Tk)'; %#ok<SAGROW>
        % Índice de manipulabilidad traslacional (Yoshikawa sobre Jv 3x4)
        J0 = robot.jacob0(qk);
        Jv = J0(1:3, :);
        M_idx(end+1, 1) = sqrt(max(0, det(Jv * Jv'))); %#ok<SAGROW>
    end
end

fig4 = figure('Name', 'Fig 4 - Trayectoria Cartesiana y Proyecciones', 'Color', 'w', 'Position', [140 60 1160 800]);
tiledlayout(2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

% 4A: Trayectoria 3D + postura inicial del robot
nexttile;
plot3(P_cart(:,1), P_cart(:,2), P_cart(:,3), '-', 'Color', [0.85 0.30 0.10], 'LineWidth', 2.6);
hold on;
plot3(rect_pts(:,1), rect_pts(:,2), rect_pts(:,3), 'ko', 'MarkerFaceColor', 'k', 'MarkerSize', 6);
plot3((P.base_dia/2)*cos(th), (P.base_dia/2)*sin(th), zeros(size(th)), 'k-', 'LineWidth', 2);
grid on; axis equal; view(38, 28);
xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
title(sprintf('Trayectoria Cartesiana 3D (\\phi = %.0f° constante)', phi_rect));
xlim([-60 220]); ylim([-110 110]); zlim([0 180]);

% 4B: Proyección XY
nexttile;
plot(P_cart(:,1), P_cart(:,2), '-', 'Color', [0.85 0.30 0.10], 'LineWidth', 2.4);
hold on;
plot(rect_pts(:,1), rect_pts(:,2), 'ko', 'MarkerFaceColor', 'k', 'MarkerSize', 6);
plot((P.base_dia/2)*cos(th), (P.base_dia/2)*sin(th), 'k-', 'LineWidth', 1.8);
xlabel('X (mm)'); ylabel('Y (mm)');
title('Proyección XY (Rectángulo exacto 50×110 mm)');
axis equal; grid on;

% 4C: Proyección XZ y YZ (verificación de altura constante Z = 65 mm)
nexttile;
plot(P_cart(:,1), P_cart(:,3), '-', 'Color', [0.15 0.45 0.78], 'LineWidth', 2.4);
hold on;
plot(P_cart(:,2), P_cart(:,3), '--', 'Color', [0.20 0.62 0.38], 'LineWidth', 2.0);
yline(65, 'k:', 'LineWidth', 1.2);
xlabel('Coordenada X o Y (mm)'); ylabel('Altura Z (mm)');
title('Proyecciones XZ (azul) y YZ (verde) — Altura Z = 65.0 mm');
legend({'Plano XZ', 'Plano YZ', 'Referencia Z=65 mm'}, 'Location', 'best');
grid on; ylim([40 90]);

% 4D: Manipulabilidad traslacional de Yoshikawa a lo largo de la ruta
nexttile;
plot(1:length(M_idx), M_idx, 'k-', 'LineWidth', 2.0);
xlabel('Paso de trayectoria'); ylabel('w = \surd det(J_v J_v^T)');
title('Manipulabilidad (Lejos de Singularidades: w > 0)');
grid on;

sgtitle('Mini-Pro 4-DOF B2 — Trayectoria Cartesiana Rectilínea y Proyecciones', 'FontSize', 14, 'FontWeight', 'bold');
exportgraphics(fig4, fullfile(outDir, 'fig4_trayectoria_cartesiana.png'), 'Resolution', 220);

fprintf('¡Listo! 4 figuras exportadas en alta resolución en:\n  %s\n', outDir);
