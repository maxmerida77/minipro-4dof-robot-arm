%% CONTROL_SERIAL_ESP32 — Gemelo Digital Sincronizado (MATLAB Peter Corke -> ESP32)
% =========================================================================
% Anima el modelo 3D en MATLAB (Peter Corke) mientras envía los ángulos en tiempo
% real al ESP32 por USB Serial usando el protocolo compacto:
%     G <q1_deg> <q2_deg> <q3_deg> <q4_deg> <grip_mm>\n
%
% MODO DRY_RUN = true  -> Corre la animación 3D sin necesidad de tener el ESP32 conectado.
% MODO DRY_RUN = false -> Envía cada punto por COM al brazo físico en vivo (Semana 3-4).

clear; clc; close all;

DRY_RUN  = true;     % Cambiar a false cuando conectes tu ESP32 por USB
COM_PORT = "COM5";   % Verificar puerto en Administrador de Dispositivos de Windows
BAUDRATE = 115200;
SEND_HZ  = 25;       % Frecuencia de sincronización MATLAB -> ESP32

[robot, P] = robot_minipro_4dof();

sp = [];
if ~DRY_RUN
    sp = serialport(COM_PORT, BAUDRATE);
    configureTerminator(sp, "LF");
    pause(2.0); % Esperar reinicio del ESP32 al abrir puerto serial
    fprintf('Conectado al ESP32 en %s @ %d baud.\n', COM_PORT, BAUDRATE);
else
    fprintf('[DRY_RUN] Ejecutando gemelo digital en simulación 3D (sin puerto COM).\n');
end

% Secuencia Pick-and-Place de demostración (X, Y, Z, phi_deg, grip_mm)
seq = [
    155,   0, 150,   0, 26;   % 1. Inicio seguro abierto
    155, -70,  75, -15, 26;   % 2. Acercamiento a objeto izquierda
    155, -70,  75, -15,  6;   % 3. Cerrar pinza (agarrar)
    155,   0, 155,   0,  6;   % 4. Elevar y trasladar
    155,  70,  75, -15,  6;   % 5. Bajar a destino derecha
    155,  70,  75, -15, 26;   % 6. Soltar objeto
    166,   0, 135,   0, 18;   % 7. Regresar a Pose Héroe
];

% Resolver IK de cada pose
Q_seq = zeros(size(seq, 1), 4);
for k = 1:size(seq, 1)
    [Q_seq(k,:), ok, msg] = ikine_minipro_4dof(seq(k,1), seq(k,2), seq(k,3), seq(k,4), true, P);
    assert(ok, 'Pose %d inalcanzable: %s', k, msg);
end

% Preparar ventana 3D
figure('Name', 'Gemelo Digital en Vivo — Mini-Pro 4-DOF B2', 'Color', 'w', 'Position', [100 100 900 680]);
ws_box = [-120 260 -240 240 0 330];
robot.plot(Q_seq(1,:), 'workspace', ws_box, 'floorlevel', 0, 'tilesize', 40, 'view', [38 24]);
hold on;
title('Gemelo Digital Sincronizado — MATLAB (Peter Corke) \rightarrow ESP32', 'FontWeight', 'bold');

dt = 1.0 / SEND_HZ;
N_steps = 30;

try
    for s = 1:size(seq, 1)-1
        q_traj = jtraj(Q_seq(s,:), Q_seq(s+1,:), N_steps);
        g_traj = linspace(seq(s,5), seq(s+1,5), N_steps);

        for i = 1:N_steps
            t0 = tic;
            qi = q_traj(i, :);
            gi = g_traj(i);

            % 1. Actualizar modelo 3D de Peter Corke
            robot.animate(qi);

            % 2. Enviar comando al ESP32 en vivo
            q_deg = rad2deg(qi);
            cmd = sprintf('G %.2f %.2f %.2f %.2f %.1f', q_deg(1), q_deg(2), q_deg(3), q_deg(4), gi);
            if ~DRY_RUN && ~isempty(sp)
                writeline(sp, cmd);
            end

            drawnow limitrate;
            rem = dt - toc(t0);
            if rem > 0, pause(rem); end
        end
    end
catch ME
    if ~isempty(sp), clear sp; end
    rethrow(ME);
end

if ~isempty(sp), clear sp; end
disp('Secuencia de gemelo digital finalizada.');
