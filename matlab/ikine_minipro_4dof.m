function [q_rad, ok, msg] = ikine_minipro_4dof(x, y, z, phi_deg, elbow_up, P)
% IKINE_MINIPRO_4DOF  Cinemática Inversa Analítica Exacta para el brazo Mini-Pro 4-DOF.
%
% Entradas:
%   x, y, z   : Coordenadas cartesianas objetivo del TCP en mm (Z=0 es el escritorio).
%   phi_deg   : Inclinación deseada de la pinza en el plano vertical del brazo (grados).
%               0° = pinza horizontal hacia afuera; -90° = pinza vertical hacia abajo.
%   elbow_up  : true (recomendado en escritorio, codo arriba) o false (codo abajo).
%   P         : Estructura de parámetros devuelta por robot_minipro_4dof() (opcional).
%
% Salidas:
%   q_rad     : Vector [q1, q2, q3, q4] en radianes.
%   ok        : true si la postura es alcanzable y respeta los límites de los MG92B.
%   msg       : Mensaje de diagnóstico.

    if nargin < 4 || isempty(phi_deg),  phi_deg = 0.0;  end
    if nargin < 5 || isempty(elbow_up), elbow_up = true; end
    if nargin < 6 || isempty(P)
        P.d1 = 85.0; P.a2 = 95.0; P.a3 = 80.0; P.a4 = 60.0;
        P.qlim = deg2rad([-90, 90; 15, 165; -135, 45; -90, 90]);
    end

    q_rad = nan(1, 4);
    ok = false;
    msg = '';

    phi = deg2rad(phi_deg);

    % 1. Base (J1) y distancia radial horizontal
    q1 = atan2(y, x);
    r  = hypot(x, y);

    % 2. Posición del centro de la muñeca (J4) restando a4 en dirección phi
    rw = r - P.a4 * cos(phi);
    zw = (z - P.d1) - P.a4 * sin(phi);

    % 3. Ley de cosenos para el brazo planar 2R (a2, a3)
    dist2 = rw^2 + zw^2;
    D = (dist2 - P.a2^2 - P.a3^2) / (2.0 * P.a2 * P.a3);

    if abs(D) > 1.0 + 1e-9
        msg = sprintf('Fuera de alcance geométrico (D = %.4f, dist_muñeca = %.1f mm).', D, sqrt(dist2));
        return;
    end
    D = max(-1.0, min(1.0, D));

    if elbow_up
        q3 = atan2(-sqrt(1.0 - D^2), D);  % Codo arriba -> q3 <= 0
    else
        q3 = atan2( sqrt(1.0 - D^2), D);  % Codo abajo  -> q3 >= 0
    end

    % 4. Hombro (J2)
    q2 = atan2(zw, rw) - atan2(P.a3 * sin(q3), P.a2 + P.a3 * cos(q3));

    % 5. Muñeca Pitch (J4) para cumplir phi = q2 + q3 + q4
    q4 = atan2(sin(phi - q2 - q3), cos(phi - q2 - q3));

    q_rad = [q1, q2, q3, q4];

    % 6. Validación contra límites físicos de los servos MG92B
    names = {'J1 (Base)', 'J2 (Hombro)', 'J3 (Codo)', 'J4 (Muñeca)'};
    tol = deg2rad(0.1);
    for i = 1:4
        if q_rad(i) < P.qlim(i, 1) - tol || q_rad(i) > P.qlim(i, 2) + tol
            msg = sprintf('%s fuera de límite: %.1f° (permitido [%.0f°, %.0f°]).', ...
                names{i}, rad2deg(q_rad(i)), rad2deg(P.qlim(i,1)), rad2deg(P.qlim(i,2)));
            return;
        end
    end

    ok = true;
    msg = 'OK';
end
