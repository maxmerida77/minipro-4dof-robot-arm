function [robot, P] = robot_minipro_4dof()
% ROBOT_MINIPRO_4DOF  Modelo cinemático exacto (Peter Corke RTB10) del brazo Mini-Pro 4-DOF B2.
%
% Concordancia al milímetro con `cad/params.py` (Single Source of Truth):
%   d1 = 85 mm  (escritorio Z=0 -> eje Hombro J2)
%   a2 = 95 mm  (Hombro J2 -> Codo J3)
%   a3 = 80 mm  (Codo J3 -> Muñeca J4)
%   a4 = 60 mm  (Muñeca J4 -> centro de agarre de pinza TCP)
%
% Convención: Denavit-Hartenberg Estándar (mm y radianes).
%   Eje Z hacia arriba, eje X hacia adelante.
%   Pose héroe de verificación: q = deg2rad([0, 68, -96, 28]) -> TCP = (166.22, 0, 135.52) mm, phi = 0°.

    P.d1 = 85.0;
    P.a2 = 95.0;
    P.a3 = 80.0;
    P.a4 = 60.0;
    P.base_dia = 94.0;

    % Límites articulares reales (MG92B 180° dentro de envolvente física segura)
    P.qlim_deg = [
        -90,   90;   % q1: Base Yaw
         15,  165;   % q2: Hombro Pitch (90° = vertical hacia arriba)
       -135,   45;   % q3: Codo Pitch (0° = alineado con L2; negativo dobla hacia adelante)
        -90,   90    % q4: Muñeca Pitch (phi = q2 + q3 + q4)
    ];
    P.qlim = deg2rad(P.qlim_deg);
    P.q_hero = deg2rad([0, 68, -96, 28]);
    P.q_home = deg2rad([0, 90, -90,  0]);

    if exist('SerialLink', 'class') ~= 8 && exist('Link', 'class') ~= 8
        error(['No se detectó la Robotics Toolbox de Peter Corke (RTB10) en el path de MATLAB.\n' ...
               'Instálala desde Add-On Explorer ("Robotics Toolbox for MATLAB" de Peter Corke)\n' ...
               'o ejecuta `startup_rvc` si ya descargaste rvctools.']);
    end

    % Definición de eslabones en Denavit-Hartenberg Estándar
    % Link('d', d, 'a', a, 'alpha', alpha, 'qlim', [min max])
    L(1) = Revolute('d', P.d1, 'a', 0.0,  'alpha',  pi/2, 'qlim', P.qlim(1, :));
    L(2) = Revolute('d', 0.0,  'a', P.a2, 'alpha',  0.0,  'qlim', P.qlim(2, :));
    L(3) = Revolute('d', 0.0,  'a', P.a3, 'alpha',  0.0,  'qlim', P.qlim(3, :));
    L(4) = Revolute('d', 0.0,  'a', P.a4, 'alpha',  0.0,  'qlim', P.qlim(4, :));

    robot = SerialLink(L, 'name', 'MiniPro-4DOF-B2');
    robot.manufacturer = 'DIY Bambu A1 / MG92B';
    robot.comment = 'Dimensiones en mm (d1=85, a2=95, a3=80, a4=60)';
end
