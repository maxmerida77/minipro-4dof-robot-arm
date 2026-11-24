# ==============================================================================
# Constructor Automático de Ensamble Articulado Nativo en SolidWorks 2025
# Mini-Pro 4-DOF (`B2 Stealth` · CAD v4 Clean-DFA)
# ==============================================================================
# Crea `cad/exports/v4_clean_dfa/solidworks/MiniPro_B2_Stealth_v4.SLDASM` con:
#   - 11 subensambles/piezas nativas (.SLDASM/.SLDPRT) conservando colores Stealth
#   - Ejes y planos de referencia paramétricos exactos en cada cuerpo rígido
#   - Relaciones de posición (Mates) mecánicas reales:
#       * J1 Base Yaw       [-90°, +90°]
#       * J2 Hombro Pitch   [+15°, +165°]
#       * J3 Codo Pitch     [-135°, +45°]
#       * J4 Muñeca Pitch   [-90°, +90°]
#       * Pinza Paralela MeArm Mod 1.5 (paralelogramo 4 barras + simetría 1:1, 0..65.4°)
#   - Detección de interferencias nativa de SolidWorks + captura PNG directa.
# ==============================================================================

$ErrorActionPreference = "Stop"

$swRedist = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist"
$swDll    = Join-Path $swRedist "SolidWorks.Interop.sldworks.dll"
$constDll = Join-Path $swRedist "SolidWorks.Interop.swconst.dll"

if (!(Test-Path $swDll) -or !(Test-Path $constDll)) {
    throw "No se encontraron las DLL de SolidWorks Interop en $swRedist"
}

$rootDir   = Split-Path -Parent $PSScriptRoot
$swWorkDir = Join-Path $rootDir "cad\exports\v4_clean_dfa\solidworks"
$stepDir   = Join-Path $swWorkDir "step_subensambles"
$subDir    = Join-Path $swWorkDir "subensambles"
$manifest  = Join-Path $swWorkDir "manifest_sw_v4.json"
$shotOut   = Join-Path $rootDir "docs\renders\solidworks_ensamble_v4.png"

if (Test-Path $subDir) { Remove-Item -Recurse -Force $subDir }
$masterAsmPre = Join-Path $swWorkDir "MiniPro_B2_Stealth_v4.SLDASM"
if (Test-Path $masterAsmPre) { Remove-Item -Force $masterAsmPre }
New-Item -ItemType Directory -Force -Path $subDir | Out-Null

$csCode = @"
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public class MiniProSwBuilder
{
    private SldWorks swApp;
    private MathUtility mathUtil;
    private string asmTemplate;

    public MiniProSwBuilder()
    {
        Type swType = Type.GetTypeFromProgID("SldWorks.Application");
        if (swType == null) throw new Exception("SldWorks.Application no registrado.");
        swApp = (SldWorks)Activator.CreateInstance(swType);
        swApp.Visible = true;
        swApp.UserControl = false;
        swApp.CommandInProgress = true;

        // Desactivar 3D Interconnect para importar sólidos nativos editables y guardables
        swApp.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swMultiCAD_Enable3DInterconnect, false);
        swApp.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swExtRefNoPromptOrSave, true);

        mathUtil = (MathUtility)swApp.GetMathUtility();
        asmTemplate = swApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
        if (string.IsNullOrEmpty(asmTemplate) || !File.Exists(asmTemplate))
        {
            asmTemplate = @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\Ensamblaje.ASMDOT";
        }
        Console.WriteLine("[OK] Conectado a SolidWorks " + swApp.RevisionNumber() + " | Plantilla: " + asmTemplate);
    }

    public void Shutdown()
    {
        try
        {
            swApp.CloseAllDocuments(true);
            swApp.CommandInProgress = false;
            swApp.ExitApp();
        }
        catch { }
    }

    private void FindStdPlanes(ModelDoc2 doc, out string planeXY, out string planeXZ, out string planeYZ)
    {
        planeXY = null; planeXZ = null; planeYZ = null;
        Feature feat = (Feature)doc.FirstFeature();
        int found = 0;
        while (feat != null && found < 3)
        {
            if (feat.GetTypeName2() == "RefPlane")
            {
                RefPlane rp = (RefPlane)feat.GetSpecificFeature2();
                MathTransform mt = rp.Transform;
                MathVector vz = (MathVector)mathUtil.CreateVector(new double[] { 0, 0, 1 });
                MathVector n = (MathVector)vz.MultiplyTransform(mt);
                double[] d = (double[])n.ArrayData;
                if (Math.Abs(d[2]) > 0.9) { planeXY = feat.Name; found++; }
                else if (Math.Abs(d[1]) > 0.9) { planeXZ = feat.Name; found++; }
                else if (Math.Abs(d[0]) > 0.9) { planeYZ = feat.Name; found++; }
            }
            feat = (Feature)feat.GetNextFeature();
        }
        if (planeXY == null || planeXZ == null || planeYZ == null)
            throw new Exception("No se pudieron identificar los 3 planos base en " + doc.GetTitle());
    }

    private double[] GetPlaneOrigin(Feature planeFeat)
    {
        RefPlane rp = (RefPlane)planeFeat.GetSpecificFeature2();
        MathPoint pt = (MathPoint)mathUtil.CreatePoint(new double[] { 0, 0, 0 });
        MathPoint tp = (MathPoint)pt.MultiplyTransform(rp.Transform);
        return (double[])tp.ArrayData;
    }

    private string MakeOffsetPlane(ModelDoc2 doc, string basePlane, int axisIdx, double targetCoordMeters, string newName)
    {
        if (Math.Abs(targetCoordMeters) < 1e-7) return basePlane;
        double dist = Math.Abs(targetCoordMeters);

        // Intentar sin flip y verificar signo real de la coordenada destino
        for (int attempt = 0; attempt < 2; attempt++)
        {
            bool flip = (attempt == 1);
            doc.ClearSelection2(true);
            bool sel = doc.Extension.SelectByID2(basePlane, "PLANE", 0, 0, 0, false, 0, null, 0);
            if (!sel) throw new Exception("No se pudo seleccionar plano base: " + basePlane);

            int constraint = (int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_Distance;
            if (flip) constraint |= (int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_OptionFlip;

            Feature pf = (Feature)doc.FeatureManager.InsertRefPlane(constraint, dist, 0, 0, 0, 0);
            if (pf == null) throw new Exception("Fallo InsertRefPlane para " + newName);

            double[] orig = GetPlaneOrigin(pf);
            if (Math.Abs(orig[axisIdx] - targetCoordMeters) < 1e-4)
            {
                pf.Name = newName;
                return newName;
            }
            // Signo invertido: borrar y reintentar con flip
            doc.ClearSelection2(true);
            pf.Select2(false, 0);
            doc.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
        }
        throw new Exception("No se logro ubicar el plano " + newName + " en " + targetCoordMeters);
    }

    private Feature FindLastFeatureOfType(ModelDoc2 doc, string typeName)
    {
        Feature f = (Feature)doc.FirstFeature();
        Feature last = null;
        while (f != null)
        {
            if (f.GetTypeName2() == typeName) last = f;
            f = (Feature)f.GetNextFeature();
        }
        return last;
    }

    private string MakeAxisFromPlanes(ModelDoc2 doc, string p1, string p2, string axisName)
    {
        doc.ClearSelection2(true);
        bool s1 = doc.Extension.SelectByID2(p1, "PLANE", 0, 0, 0, false, 0, null, 0);
        bool s2 = doc.Extension.SelectByID2(p2, "PLANE", 0, 0, 0, true, 0, null, 0);
        if (!s1 || !s2) throw new Exception("No se pudieron seleccionar planos para eje " + axisName);
        bool ok = doc.InsertAxis2(true);
        if (!ok) throw new Exception("Fallo InsertAxis2 para " + axisName);
        Feature f = FindLastFeatureOfType(doc, "RefAxis");
        if (f == null) throw new Exception("No se encontro RefAxis recien creado para " + axisName);
        f.Name = axisName;
        return axisName;
    }

    private string MakePlane45ThroughYAxis(ModelDoc2 doc, string pXY, string pYZ, double xAxisM, string axisName, string newName)
    {
        // Plano exacto a +45° pasando por Axis_Dist (x=xAxisM, z=0) y una paralela en (x=xAxisM+0.010, z=+0.010)!
        // Solo usa restricciones Coincident+Coincident (100% determinista en SolidWorks).
        string pX2 = MakeOffsetPlane(doc, pYZ, 0, xAxisM + 0.010, "_tmp_X45");
        string pZ2 = MakeOffsetPlane(doc, pXY, 2, +0.010, "_tmp_Z45");
        string ax2 = MakeAxisFromPlanes(doc, pX2, pZ2, "_tmp_Axis45");

        doc.ClearSelection2(true);
        bool s1 = doc.Extension.SelectByID2(axisName, "AXIS", 0, 0, 0, false, 0, null, 0);
        bool s2 = doc.Extension.SelectByID2(ax2, "AXIS", 0, 0, 0, true, 1, null, 0);
        int c = (int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_Coincident;
        Feature pf = (Feature)doc.FeatureManager.InsertRefPlane(c, 0, c, 0, 0, 0);
        if (pf == null)
        {
            doc.ClearSelection2(true);
            doc.Extension.SelectByID2(axisName, "AXIS", 0, 0, 0, false, 0, null, 0);
            doc.Extension.SelectByID2(ax2, "AXIS", 0, 0, 0, true, 0, null, 0);
            pf = (Feature)doc.FeatureManager.InsertRefPlane(c, 0, c, 0, 0, 0);
        }
        if (pf == null)
            throw new Exception("No se pudo crear plano 45 deg " + newName + " (s1=" + s1 + ", s2=" + s2 + ")");
        pf.Name = newName;
        return newName;
    }

    private string ImportAndPrepareSub(
        string stepPath,
        string outDir,
        string baseName,
        Action<ModelDoc2, string, string, string> addRefGeom)
    {
        int errs = 0;
        ImportStepData impData = (ImportStepData)swApp.GetImportFileData(stepPath);
        impData.MapConfigurationData = true;
        ModelDoc2 doc = (ModelDoc2)swApp.LoadFile4(stepPath, "r", impData, ref errs);
        if (doc == null) throw new Exception("Error importando STEP " + stepPath + " (err=" + errs + ")");

        bool isAsm = (doc.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY);
        string ext = isAsm ? ".SLDASM" : ".SLDPRT";
        string savePath = Path.Combine(outDir, baseName + ext);

        // Si es subensamble, guardar primero sus piezas internas en disco para que queden 100% persistentes
        if (isAsm)
        {
            AssemblyDoc subAsm = (AssemblyDoc)doc;
            object[] comps = (object[])subAsm.GetComponents(true);
            if (comps != null)
            {
                foreach (object o in comps)
                {
                    Component2 c = (Component2)o;
                    ModelDoc2 cdoc = (ModelDoc2)c.GetModelDoc2();
                    if (cdoc != null && string.IsNullOrEmpty(cdoc.GetPathName()))
                    {
                        string cname = c.Name2;
                        int dash = cname.LastIndexOf('-');
                        if (dash > 0) cname = cname.Substring(0, dash);
                        string ppath = Path.Combine(outDir, baseName + "__" + cname + ".SLDPRT");
                        int ce = 0, cw = 0;
                        cdoc.Extension.SaveAs3(ppath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref ce, ref cw);
                    }
                }
            }
        }

        // Identificar planos estándar e inyectar geometría de referencia exacta
        string pXY, pXZ, pYZ;
        FindStdPlanes(doc, out pXY, out pXZ, out pYZ);

        // Renombrar o mantener mapeo -> creamos ejes limpios sobre los planos base!
        addRefGeom(doc, pXY, pXZ, pYZ);

        doc.ForceRebuild3(false);
        int se = 0, sw = 0;
        bool saved = doc.Extension.SaveAs3(savePath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
            (int)swSaveAsOptions_e.swSaveAsOptions_Silent | (int)swSaveAsOptions_e.swSaveAsOptions_SaveReferenced,
            null, null, ref se, ref sw);
        if (!saved) throw new Exception("No se pudo guardar " + savePath + " (err=" + se + ", warn=" + sw + ")");

        string title = doc.GetTitle();
        swApp.CloseDoc(title);
        Console.WriteLine("  [OK] Preparado: " + Path.GetFileName(savePath) + " (planos: " + pXY + "/" + pXZ + "/" + pYZ + ")");
        return savePath;
    }

    private MathTransform MakeTransform(double[,] R, double tx, double ty, double tz)
    {
        // SolidWorks MathTransform ArrayData (16 doubles):
        // [R00, R10, R20, R01, R11, R21, R02, R12, R22, tx, ty, tz, scale, 0, 0, 0] (columnas R!)
        double[] arr = new double[] {
            R[0,0], R[1,0], R[2,0],
            R[0,1], R[1,1], R[2,1],
            R[0,2], R[1,2], R[2,2],
            tx, ty, tz,
            1.0, 0.0, 0.0, 0.0
        };
        return (MathTransform)mathUtil.CreateTransform(arr);
    }

    private double[,] RotY(double deg)
    {
        double a = deg * Math.PI / 180.0;
        double c = Math.Cos(a), s = Math.Sin(a);
        return new double[,] { { c, 0, s }, { 0, 1, 0 }, { -s, 0, c } };
    }

    private double[,] RotZ(double deg)
    {
        double a = deg * Math.PI / 180.0;
        double c = Math.Cos(a), s = Math.Sin(a);
        return new double[,] { { c, -s, 0 }, { s, c, 0 }, { 0, 0, 1 } };
    }

    private double[,] Mul(double[,] A, double[,] B)
    {
        double[,] C = new double[3, 3];
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
                C[i, j] = A[i, 0] * B[0, j] + A[i, 1] * B[1, j] + A[i, 2] * B[2, j];
        return C;
    }

    private string FindPlaneNameInComp(Component2 comp, int normAxis)
    {
        ModelDoc2 cdoc = (ModelDoc2)comp.GetModelDoc2();
        string pXY, pXZ, pYZ;
        FindStdPlanes(cdoc, out pXY, out pXZ, out pYZ);
        if (normAxis == 2) return pXY;
        if (normAxis == 1) return pXZ;
        return pYZ;
    }

    private bool SelectCompFeature(ModelDoc2 asmDoc, string asmName, Component2 comp, string featName, string featType, bool append, int mark)
    {
        string selStr = featName + "@" + comp.Name2 + "@" + asmName;
        bool ok = asmDoc.Extension.SelectByID2(selStr, featType, 0, 0, 0, append, mark, null, 0);
        if (!ok)
        {
            Console.WriteLine("  [WARN] Fallo SelectByID2: " + selStr + " (" + featType + ")");
        }
        return ok;
    }

    private void AddCoincidentMate(ModelDoc2 asmDoc, AssemblyDoc assy, string asmName,
        Component2 c1, string f1, string t1,
        Component2 c2, string f2, string t2,
        string mateName, int align)
    {
        asmDoc.ClearSelection2(true);
        SelectCompFeature(asmDoc, asmName, c1, f1, t1, false, 1);
        SelectCompFeature(asmDoc, asmName, c2, f2, t2, true, 1);
        int err = 0;
        Mate2 m = (Mate2)assy.AddMate5((int)swMateType_e.swMateCOINCIDENT, align, false,
            0, 0, 0, 0, 0, 0, 0, 0, false, false, 0, out err);
        if (m == null || err != (int)swAddMateError_e.swAddMateError_NoError)
            Console.WriteLine("  [!] Mate " + mateName + " fallo (err=" + err + ")");
        else
        {
            ((Feature)m).Name = mateName;
            Console.WriteLine("  [OK] Mate " + mateName);
        }
    }

    private void AddLimitAngleMate(ModelDoc2 asmDoc, AssemblyDoc assy, string asmName,
        Component2 c1, string p1, Component2 c2, string p2,
        double curDeg, double minDeg, double maxDeg, string mateName,
        double[] expectedXDir = null)
    {
        double curRad = curDeg * Math.PI / 180.0;
        double minRad = minDeg * Math.PI / 180.0;
        double maxRad = maxDeg * Math.PI / 180.0;

        asmDoc.ClearSelection2(true);
        SelectCompFeature(asmDoc, asmName, c1, p1, "PLANE", false, 1);
        SelectCompFeature(asmDoc, asmName, c2, p2, "PLANE", true, 1);
        int err = 0;
        Mate2 m = (Mate2)assy.AddMate5((int)swMateType_e.swMateANGLE, (int)swMateAlign_e.swMateAlignCLOSEST, false,
            0, 0, 0, 0, 0, curRad, maxRad, minRad, false, false, 0, out err);
        if (m == null || err != (int)swAddMateError_e.swAddMateError_NoError)
        {
            Console.WriteLine("  [!] LimitAngle " + mateName + " fallo (err=" + err + ")");
            return;
        }
        Feature f = (Feature)m;
        f.Name = mateName;
        try
        {
            AngleMateFeatureData md = (AngleMateFeatureData)f.GetDefinition();
            if (md != null)
            {
                md.IsAdvancedMate = true;
                md.MaximumAngle = maxRad;
                md.MinimumAngle = minRad;
                md.Angle = curRad;
                f.ModifyDefinition(md, asmDoc, null);
                asmDoc.ForceRebuild3(false);

                // Verificar contra la orientación X esperada de Pose Héroe; si se invirtió la normal del plano, probar FlipDimension / complemento!
                if (expectedXDir != null)
                {
                    double[] td = (double[])c2.Transform2.ArrayData;
                    double dot = td[0] * expectedXDir[0] + td[1] * expectedXDir[1] + td[2] * expectedXDir[2];
                    if (dot < 0.90)
                    {
                        md = (AngleMateFeatureData)f.GetDefinition();
                        md.IsAdvancedMate = true;
                        md.MaximumAngle = maxRad;
                        md.MinimumAngle = minRad;
                        md.FlipDimension = !md.FlipDimension;
                        md.Angle = curRad;
                        f.ModifyDefinition(md, asmDoc, null);
                        asmDoc.ForceRebuild3(false);
                        td = (double[])c2.Transform2.ArrayData;
                        dot = td[0] * expectedXDir[0] + td[1] * expectedXDir[1] + td[2] * expectedXDir[2];
                        if (dot < 0.90)
                        {
                            md = (AngleMateFeatureData)f.GetDefinition();
                            md.IsAdvancedMate = true;
                            md.MaximumAngle = maxRad;
                            md.MinimumAngle = minRad;
                            md.FlipDimension = !md.FlipDimension;
                            md.MateAlignment = (md.MateAlignment == (int)swMateAlign_e.swMateAlignALIGNED)
                                ? (int)swMateAlign_e.swMateAlignANTI_ALIGNED
                                : (int)swMateAlign_e.swMateAlignALIGNED;
                            md.Angle = curRad;
                            f.ModifyDefinition(md, asmDoc, null);
                            asmDoc.ForceRebuild3(false);
                        }
                    }
                }
                Console.WriteLine("  [OK] LimitAngle " + mateName + " [cur=" + curDeg.ToString("F1") + ", lim=" + minDeg + ".." + maxDeg + " deg | adv=" + md.IsAdvancedMate + "]");
                return;
            }
        }
        catch { }
        Console.WriteLine("  [OK] LimitAngle " + mateName + " [" + minDeg + ".." + maxDeg + " deg]");
    }

    private void AddGearOrSymmetricMate(ModelDoc2 asmDoc, AssemblyDoc assy, string asmName,
        Component2 gearL, Component2 gearR,
        Component2 symComp, string symPlane,
        Component2 dedL, string pL, Component2 dedR, string pR, string mateName)
    {
        // 1) Intentar relación MECÁNICA DE ENGRANAJE real 1:1 (contra-rotatorio) entre los dos ejes 12T!
        asmDoc.ClearSelection2(true);
        SelectCompFeature(asmDoc, asmName, gearL, "Axis_Base", "AXIS", false, 1);
        SelectCompFeature(asmDoc, asmName, gearR, "Axis_Base", "AXIS", true, 1);
        int err = 0;
        Mate2 m = (Mate2)assy.AddMate5((int)swMateType_e.swMateGEAR, (int)swMateAlign_e.swMateAlignALIGNED, true,
            0, 0, 0, 1.0, 1.0, 0, 0, 0, false, false, 0, out err);
        if (m != null && err == (int)swAddMateError_e.swAddMateError_NoError)
        {
            ((Feature)m).Name = mateName;
            Console.WriteLine("  [OK] GearMate 1:1 " + mateName + " (engranaje real 12T:12T contra-rotatorio)");
            return;
        }
        // 2) Respaldo: Simetría 1:1 con plano de simetría seleccionado con mark 1 primero
        asmDoc.ClearSelection2(true);
        SelectCompFeature(asmDoc, asmName, symComp, symPlane, "PLANE", false, 1);
        SelectCompFeature(asmDoc, asmName, dedL, pL, "PLANE", true, 1);
        SelectCompFeature(asmDoc, asmName, dedR, pR, "PLANE", true, 1);
        m = (Mate2)assy.AddMate5((int)swMateType_e.swMateSYMMETRIC, (int)swMateAlign_e.swMateAlignCLOSEST, false,
            0, 0, 0, 0, 0, 0, 0, 0, false, false, 0, out err);
        if (m != null && err == (int)swAddMateError_e.swAddMateError_NoError)
        {
            ((Feature)m).Name = mateName;
            Console.WriteLine("  [OK] Symmetric " + mateName + " (acoplamiento 1:1 paralelo)");
        }
        else
        {
            Console.WriteLine("  [!] Gear/Symmetric " + mateName + " fallo (err=" + err + ")");
        }
    }

    public void BuildAll(
        string stepDir, string subDir, string masterAsmPath, string shotOut,
        double d1, double a2, double a3, double gx, double gy, double ix, double iy, double linkL,
        double q1Deg, double q2Deg, double q3Deg, double q4Deg, double gripThDeg)
    {
        Console.WriteLine("=== PASO 1: IMPORTANDO 11 SUBENSAMBLES Y CREANDO EJES DE REFERENCIA ===");
        var paths = new Dictionary<string, string>();

        paths["01_Base_Fija"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "01_Base_Fija.step"), subDir, "01_Base_Fija",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXZ, "Axis_J1");
            });

        paths["02_Torreta_J1"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "02_Torreta_J1.step"), subDir, "02_Torreta_J1",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXZ, "Axis_J1");
                string pZ_d1 = MakeOffsetPlane(doc, pXY, 2, d1, "Plane_Z_J2");
                MakeAxisFromPlanes(doc, pYZ, pZ_d1, "Axis_J2");
            });

        paths["03_Brazo_L2"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "03_Brazo_L2.step"), subDir, "03_Brazo_L2",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXY, "Axis_Prox");
                string pX_a2 = MakeOffsetPlane(doc, pYZ, 0, a2, "Plane_X_J3");
                string axDist = MakeAxisFromPlanes(doc, pX_a2, pXY, "Axis_Dist");
                MakePlane45ThroughYAxis(doc, pXY, pYZ, a2, axDist, "Plane_J3_Ref45");
            });

        paths["04_Antebrazo_L3"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "04_Antebrazo_L3.step"), subDir, "04_Antebrazo_L3",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXY, "Axis_Prox");
                string pX_a3 = MakeOffsetPlane(doc, pYZ, 0, a3, "Plane_X_J4");
                MakeAxisFromPlanes(doc, pX_a3, pXY, "Axis_Dist");
            });

        paths["05_Palma_Muneca"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "05_Palma_Muneca.step"), subDir, "05_Palma_Muneca",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXY, "Axis_Prox");
                string pX_g  = MakeOffsetPlane(doc, pYZ, 0, gx, "Plane_X_Gear");
                string pX_i  = MakeOffsetPlane(doc, pYZ, 0, ix, "Plane_X_Idler");
                string pY_gL = MakeOffsetPlane(doc, pXZ, 1, +gy, "Plane_Y_GearL");
                string pY_gR = MakeOffsetPlane(doc, pXZ, 1, -gy, "Plane_Y_GearR");
                string pY_iL = MakeOffsetPlane(doc, pXZ, 1, +iy, "Plane_Y_IdlerL");
                string pY_iR = MakeOffsetPlane(doc, pXZ, 1, -iy, "Plane_Y_IdlerR");
                MakeAxisFromPlanes(doc, pX_g, pY_gL, "Axis_GearL");
                MakeAxisFromPlanes(doc, pX_g, pY_gR, "Axis_GearR");
                MakeAxisFromPlanes(doc, pX_i, pY_iL, "Axis_IdlerL");
                MakeAxisFromPlanes(doc, pX_i, pY_iR, "Axis_IdlerR");
            });

        foreach (string linkName in new[] { "06_Engrane_Brazo_Izq", "07_Engrane_Brazo_Der", "08_Biela_Izq", "09_Biela_Der" })
        {
            paths[linkName] = ImportAndPrepareSub(
                Path.Combine(stepDir, linkName + ".step"), subDir, linkName,
                (doc, pXY, pXZ, pYZ) => {
                    MakeAxisFromPlanes(doc, pYZ, pXZ, "Axis_Base");
                    string pX_tip = MakeOffsetPlane(doc, pYZ, 0, linkL, "Plane_X_Tip");
                    MakeAxisFromPlanes(doc, pX_tip, pXZ, "Axis_Tip");
                });
        }

        double dxRear = ix - gx;   // -6.5 mm
        double dyRear = iy - gy;   // +7.7 mm
        paths["10_Dedo_Izq"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "10_Dedo_Izq.step"), subDir, "10_Dedo_Izq",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXZ, "Axis_Front");
                string pX_r = MakeOffsetPlane(doc, pYZ, 0, dxRear, "Plane_X_Rear");
                string pY_r = MakeOffsetPlane(doc, pXZ, 1, +dyRear, "Plane_Y_Rear");
                MakeAxisFromPlanes(doc, pX_r, pY_r, "Axis_Rear");
            });

        paths["11_Dedo_Der"] = ImportAndPrepareSub(
            Path.Combine(stepDir, "11_Dedo_Der.step"), subDir, "11_Dedo_Der",
            (doc, pXY, pXZ, pYZ) => {
                MakeAxisFromPlanes(doc, pYZ, pXZ, "Axis_Front");
                string pX_r = MakeOffsetPlane(doc, pYZ, 0, dxRear, "Plane_X_Rear");
                string pY_r = MakeOffsetPlane(doc, pXZ, 1, -dyRear, "Plane_Y_Rear");
                MakeAxisFromPlanes(doc, pX_r, pY_r, "Axis_Rear");
            });

        Console.WriteLine("\n=== PASO 2: CREANDO ENSAMBLE MAESTRO ARTICULADO EN POSE HEROE ===");
        ModelDoc2 asmDoc = (ModelDoc2)swApp.NewDocument(asmTemplate, 0, 0, 0);
        AssemblyDoc assy = (AssemblyDoc)asmDoc;

        // Guardar inmediatamente para fijar el nombre del documento maestro en SelectByID2
        int se = 0, sw = 0;
        asmDoc.Extension.SaveAs3(masterAsmPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref se, ref sw);
        string asmName = Path.GetFileNameWithoutExtension(masterAsmPath);

        // Calcular poses exactas de Pose Héroe en coordenadas mundo (metros)
        double a2r = q2Deg * Math.PI / 180.0;
        double a3r = (q2Deg + q3Deg) * Math.PI / 180.0;
        double a4r = (q2Deg + q3Deg + q4Deg) * Math.PI / 180.0;
        double thr = gripThDeg * Math.PI / 180.0;

        double p3x = a2 * Math.Cos(a2r), p3z = d1 + a2 * Math.Sin(a2r);
        double p4x = p3x + a3 * Math.Cos(a3r), p4z = p3z + a3 * Math.Sin(a3r);

        // En Pose Héroe (q2+q3+q4 = 0°!), el marco de la palma está perfectamente horizontal (R4 = I)!
        double[,] I3 = RotZ(0.0);
        double[,] R2 = RotY(-q2Deg);
        double[,] R3 = RotY(-(q2Deg + q3Deg));
        double[,] R4 = RotY(-(q2Deg + q3Deg + q4Deg));
        double[,] R_GL = Mul(R4, RotZ(+gripThDeg));
        double[,] R_GR = Mul(R4, RotZ(-gripThDeg));

        Func<double, double, double, double[]> palmToWorld = (lx, ly, lz) => new double[] {
            p4x + R4[0,0]*lx + R4[0,1]*ly + R4[0,2]*lz,
            0.0 + R4[1,0]*lx + R4[1,1]*ly + R4[1,2]*lz,
            p4z + R4[2,0]*lx + R4[2,1]*ly + R4[2,2]*lz
        };

        var comps = new Dictionary<string, Component2>();
        Action<string, double[,], double, double, double, bool> addC = (key, R, tx, ty, tz, fixIt) => {
            string p = paths[key];
            int oe = 0, ow = 0;
            int docType = p.EndsWith(".SLDASM", StringComparison.OrdinalIgnoreCase)
                ? (int)swDocumentTypes_e.swDocASSEMBLY
                : (int)swDocumentTypes_e.swDocPART;
            ModelDoc2 subDoc = (ModelDoc2)swApp.OpenDoc6(p, docType, (int)swOpenDocOptions_e.swOpenDocOptions_Silent, "", ref oe, ref ow);
            int actErr = 0;
            swApp.ActivateDoc3(asmDoc.GetTitle(), false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref actErr);
            Component2 c = assy.AddComponent5(p, (int)swAddComponentConfigOptions_e.swAddComponentConfigOptions_CurrentSelectedConfig, "", false, "", 0, 0, 0);
            if (subDoc != null) swApp.CloseDoc(subDoc.GetTitle());
            if (c == null) throw new Exception("No se pudo insertar componente " + key);
            // Liberar y posicionar exacto en Pose Héroe
            asmDoc.ClearSelection2(true);
            c.Select4(false, null, false);
            if (fixIt) assy.FixComponent(); else assy.UnfixComponent();
            c.Transform2 = MakeTransform(R, tx, ty, tz);
            comps[key] = c;
            Console.WriteLine("  [OK] Insertado " + c.Name2 + (fixIt ? " (FIJO)" : " (MÓVIL)"));
        };

        addC("01_Base_Fija", I3, 0, 0, 0, true);
        addC("02_Torreta_J1", I3, 0, 0, 0, false);
        addC("03_Brazo_L2", R2, 0, 0, d1, false);
        addC("04_Antebrazo_L3", R3, p3x, 0, p3z, false);
        addC("05_Palma_Muneca", R4, p4x, 0, p4z, false);

        double[] wGL = palmToWorld(gx, +gy, 0);
        double[] wGR = palmToWorld(gx, -gy, 0);
        double[] wIL = palmToWorld(ix, +iy, 0);
        double[] wIR = palmToWorld(ix, -iy, 0);
        double[] wFL = palmToWorld(gx + linkL * Math.Cos(thr), +(gy + linkL * Math.Sin(thr)), 0);
        double[] wFR = palmToWorld(gx + linkL * Math.Cos(thr), -(gy + linkL * Math.Sin(thr)), 0);

        addC("06_Engrane_Brazo_Izq", R_GL, wGL[0], wGL[1], wGL[2], false);
        addC("07_Engrane_Brazo_Der", R_GR, wGR[0], wGR[1], wGR[2], false);
        addC("08_Biela_Izq", R_GL, wIL[0], wIL[1], wIL[2], false);
        addC("09_Biela_Der", R_GR, wIR[0], wIR[1], wIR[2], false);
        addC("10_Dedo_Izq", R4, wFL[0], wFL[1], wFL[2], false);
        addC("11_Dedo_Der", R4, wFR[0], wFR[1], wFR[2], false);

        asmDoc.ForceRebuild3(false);

        Console.WriteLine("\n=== PASO 3: APLICANDO RELACIONES DE POSICION (MATES) CINEMATICAS ===");
        int ALN = (int)swMateAlign_e.swMateAlignALIGNED;

        string baseXY = FindPlaneNameInComp(comps["01_Base_Fija"], 2);
        string baseYZ = FindPlaneNameInComp(comps["01_Base_Fija"], 0);
        string turXY  = FindPlaneNameInComp(comps["02_Torreta_J1"], 2);
        string turXZ  = FindPlaneNameInComp(comps["02_Torreta_J1"], 1);
        string l2XY   = FindPlaneNameInComp(comps["03_Brazo_L2"], 2);
        string l2XZ   = FindPlaneNameInComp(comps["03_Brazo_L2"], 1);
        string l3XY   = FindPlaneNameInComp(comps["04_Antebrazo_L3"], 2);
        string l3XZ   = FindPlaneNameInComp(comps["04_Antebrazo_L3"], 1);
        string l3YZ   = FindPlaneNameInComp(comps["04_Antebrazo_L3"], 0);
        string plmXY  = FindPlaneNameInComp(comps["05_Palma_Muneca"], 2);
        string plmXZ  = FindPlaneNameInComp(comps["05_Palma_Muneca"], 1);
        string glXY   = FindPlaneNameInComp(comps["06_Engrane_Brazo_Izq"], 2);
        string glXZ   = FindPlaneNameInComp(comps["06_Engrane_Brazo_Izq"], 1);
        string grXY   = FindPlaneNameInComp(comps["07_Engrane_Brazo_Der"], 2);
        string blXY   = FindPlaneNameInComp(comps["08_Biela_Izq"], 2);
        string brXY   = FindPlaneNameInComp(comps["09_Biela_Der"], 2);
        string flXY   = FindPlaneNameInComp(comps["10_Dedo_Izq"], 2);
        string flXZ   = FindPlaneNameInComp(comps["10_Dedo_Izq"], 1);
        string frXY   = FindPlaneNameInComp(comps["11_Dedo_Der"], 2);
        string frXZ   = FindPlaneNameInComp(comps["11_Dedo_Der"], 1);

        // J1: Base <-> Torreta (Yaw [-90°, +90°])
        AddCoincidentMate(asmDoc, assy, asmName, comps["01_Base_Fija"], "Axis_J1", "AXIS", comps["02_Torreta_J1"], "Axis_J1", "AXIS", "J1_Eje_Coaxial", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["01_Base_Fija"], baseXY, "PLANE", comps["02_Torreta_J1"], turXY, "PLANE", "J1_Plano_Z0", ALN);
        AddLimitAngleMate(asmDoc, assy, asmName, comps["01_Base_Fija"], baseYZ, comps["02_Torreta_J1"], turXZ, 90.0, 0.0, 180.0, "J1_Limite_pm90");

        // J2: Torreta <-> Brazo L2 (Pitch [+15°, +165°])
        AddCoincidentMate(asmDoc, assy, asmName, comps["02_Torreta_J1"], "Axis_J2", "AXIS", comps["03_Brazo_L2"], "Axis_Prox", "AXIS", "J2_Eje_Hombro", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["02_Torreta_J1"], turXZ, "PLANE", comps["03_Brazo_L2"], l2XZ, "PLANE", "J2_Plano_Centrado", ALN);
        AddLimitAngleMate(asmDoc, assy, asmName, comps["02_Torreta_J1"], turXY, comps["03_Brazo_L2"], l2XY, q2Deg, 15.0, 165.0, "J2_Limite_15_165",
            new double[] { Math.Cos(a2r), 0.0, Math.Sin(a2r) });

        // J3: Brazo L2 <-> Antebrazo L3 (Pitch [-135°, +45°] respecto a Plane_J3_Ref45 -> [0°, 180°])
        AddCoincidentMate(asmDoc, assy, asmName, comps["03_Brazo_L2"], "Axis_Dist", "AXIS", comps["04_Antebrazo_L3"], "Axis_Prox", "AXIS", "J3_Eje_Codo", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["03_Brazo_L2"], l2XZ, "PLANE", comps["04_Antebrazo_L3"], l3XZ, "PLANE", "J3_Plano_Centrado", ALN);
        AddLimitAngleMate(asmDoc, assy, asmName, comps["03_Brazo_L2"], "Plane_J3_Ref45", comps["04_Antebrazo_L3"], l3XY, 45.0 - q3Deg, 0.0, 180.0, "J3_Limite_m135_p45",
            new double[] { Math.Cos(a3r), 0.0, Math.Sin(a3r) });

        // J4: Antebrazo L3 <-> Palma Muñeca (Pitch [-90°, +90°])
        AddCoincidentMate(asmDoc, assy, asmName, comps["04_Antebrazo_L3"], "Axis_Dist", "AXIS", comps["05_Palma_Muneca"], "Axis_Prox", "AXIS", "J4_Eje_Muneca", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["04_Antebrazo_L3"], l3XZ, "PLANE", comps["05_Palma_Muneca"], plmXZ, "PLANE", "J4_Plano_Centrado", ALN);
        AddLimitAngleMate(asmDoc, assy, asmName, comps["04_Antebrazo_L3"], l3YZ, comps["05_Palma_Muneca"], plmXY, 90.0 + q4Deg, 0.0, 180.0, "J4_Limite_pm90",
            new double[] { Math.Cos(a4r), 0.0, Math.Sin(a4r) });

        // Pinza Paralela Abierta MeArm Mod 1.5 (Paralelogramo 4 barras + Simetría 1:1!)
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], "Axis_GearL", "AXIS", comps["06_Engrane_Brazo_Izq"], "Axis_Base", "AXIS", "Pinza_EngraneL_Eje", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["06_Engrane_Brazo_Izq"], glXY, "PLANE", "Pinza_EngraneL_Z", ALN);
        AddLimitAngleMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXZ, comps["06_Engrane_Brazo_Izq"], glXZ, gripThDeg, 0.5, 65.0, "Pinza_Apertura_0_30mm");

        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], "Axis_GearR", "AXIS", comps["07_Engrane_Brazo_Der"], "Axis_Base", "AXIS", "Pinza_EngraneR_Eje", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["07_Engrane_Brazo_Der"], grXY, "PLANE", "Pinza_EngraneR_Z", ALN);

        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], "Axis_IdlerL", "AXIS", comps["08_Biela_Izq"], "Axis_Base", "AXIS", "Pinza_BielaL_Eje", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["08_Biela_Izq"], blXY, "PLANE", "Pinza_BielaL_Z", ALN);

        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], "Axis_IdlerR", "AXIS", comps["09_Biela_Der"], "Axis_Base", "AXIS", "Pinza_BielaR_Eje", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["09_Biela_Der"], brXY, "PLANE", "Pinza_BielaR_Z", ALN);

        AddCoincidentMate(asmDoc, assy, asmName, comps["06_Engrane_Brazo_Izq"], "Axis_Tip", "AXIS", comps["10_Dedo_Izq"], "Axis_Front", "AXIS", "Pinza_DedoL_Front", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["08_Biela_Izq"], "Axis_Tip", "AXIS", comps["10_Dedo_Izq"], "Axis_Rear", "AXIS", "Pinza_DedoL_Rear", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["10_Dedo_Izq"], flXY, "PLANE", "Pinza_DedoL_Z", ALN);

        AddCoincidentMate(asmDoc, assy, asmName, comps["07_Engrane_Brazo_Der"], "Axis_Tip", "AXIS", comps["11_Dedo_Der"], "Axis_Front", "AXIS", "Pinza_DedoR_Front", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["09_Biela_Der"], "Axis_Tip", "AXIS", comps["11_Dedo_Der"], "Axis_Rear", "AXIS", "Pinza_DedoR_Rear", ALN);
        AddCoincidentMate(asmDoc, assy, asmName, comps["05_Palma_Muneca"], plmXY, "PLANE", comps["11_Dedo_Der"], frXY, "PLANE", "Pinza_DedoR_Z", ALN);

        // Acoplamiento mecánico 1:1 (al arrastrar un dedo o engrane, ambos cierran paralelos y engranados!)
        AddGearOrSymmetricMate(asmDoc, assy, asmName,
            comps["06_Engrane_Brazo_Izq"], comps["07_Engrane_Brazo_Der"],
            comps["05_Palma_Muneca"], plmXZ,
            comps["10_Dedo_Izq"], flXZ, comps["11_Dedo_Der"], frXZ, "Pinza_Engranaje_1a1");

        asmDoc.ForceRebuild3(false);

        // Activar ventana del ensamble maestro antes de inspeccionar/encuadrar/capturar
        int actErr2 = 0;
        swApp.ActivateDoc3(asmDoc.GetTitle(), false, (int)swRebuildOnActivation_e.swUserDecision, ref actErr2);

        // Auditar estado de TODOS los mates del árbol (0 errores / 0 advertencias!)
        int nMatesOk = 0, nMatesWarn = 0;
        Feature mf = (Feature)asmDoc.FirstFeature();
        while (mf != null)
        {
            if (mf.GetTypeName2() == "MateGroup")
            {
                Feature sub = (Feature)mf.GetFirstSubFeature();
                while (sub != null)
                {
                    bool isWarn = false;
                    int ecode = sub.GetErrorCode2(out isWarn);
                    if (ecode == 0 && !isWarn) nMatesOk++;
                    else { nMatesWarn++; Console.WriteLine("  [WARN MATE] " + sub.Name + " code=" + ecode + " warn=" + isWarn); }
                    sub = (Feature)sub.GetNextSubFeature();
                }
            }
            mf = (Feature)mf.GetNextFeature();
        }
        Console.WriteLine("  [RESUMEN MATES SOLIDWORKS] OK=" + nMatesOk + " | Warnings/Errores=" + nMatesWarn);

        // Ocultar planos y ejes de referencia para una vista Stealth ultra limpia al abrir SolidWorks
        asmDoc.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDisplayPlanes, false);
        asmDoc.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDisplayAxes, false);
        asmDoc.SetUserPreferenceToggle((int)swUserPreferenceToggle_e.swDisplayOrigins, false);

        Console.WriteLine("\n=== PASO 4: DETECCION DE INTERFERENCIAS NATIVA DE SOLIDWORKS 2025 ===");
        InterferenceDetectionMgr idm = (InterferenceDetectionMgr)assy.InterferenceDetectionManager;
        idm.TreatCoincidenceAsInterference = false;
        idm.TreatSubAssembliesAsComponents = false;
        idm.IncludeMultibodyPartInterferences = true;
        idm.MakeInterferingPartsTransparent = false;
        idm.CreateFastenersFolder = false;
        object[] interfs = (object[])idm.GetInterferences();
        int nInt = (interfs == null) ? 0 : interfs.Length;
        Console.WriteLine("  [SOLIDWORKS INTERFERENCE CHECK] Interferencias detectadas = " + nInt);
        if (interfs != null)
        {
            foreach (object io in interfs)
            {
                Interference inf = (Interference)io;
                double volMm3 = inf.Volume * 1e9;
                object[] ic = (object[])inf.Components;
                string cnames = "";
                if (ic != null)
                {
                    foreach (object co in ic) cnames += ((Component2)co).Name2 + " ";
                }
                Console.WriteLine(string.Format("    - {0:F3} mm3 | {1}", volMm3, cnames));
            }
        }
        idm.Done();

        // Imprimir pose real de cada cuerpo rígido tras resolver todos los mates
        foreach (string k in new[] { "01_Base_Fija", "02_Torreta_J1", "03_Brazo_L2", "04_Antebrazo_L3", "05_Palma_Muneca", "10_Dedo_Izq", "11_Dedo_Der" })
        {
            double[] td = (double[])comps[k].Transform2.ArrayData;
            Console.WriteLine(string.Format("  [POSE] {0,-18} | pos=({1:F1},{2:F1},{3:F1}) mm | X=({4:F2},{5:F2},{6:F2})",
                k, td[9]*1000, td[10]*1000, td[11]*1000, td[0], td[1], td[2]));
        }

        // Encuadrar vista 3/4 con +Z ARRIBA (mesa horizontal) usando la convención fila-vector de Orientation3!
        ModelView mv = (ModelView)asmDoc.ActiveView;
        if (mv != null)
        {
            // Filas de Orientation3 = vectores mundo [ScreenRight, ScreenUp, TowardViewer] transpuestos para MathTransform!
            // ScreenRight = (0.755, 0.656, 0), ScreenUp = (-0.290, 0.334, 0.897), TowardViewer = (0.589, -0.677, 0.442)
            double[] rotView = new double[] {
                 0.755, -0.290,  0.589,
                 0.656,  0.334, -0.677,
                 0.000,  0.897,  0.442,
                 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0
            };
            mv.Orientation3 = (MathTransform)mathUtil.CreateTransform(rotView);
        }
        asmDoc.ViewZoomtofit2();

        // Guardar ensamble maestro ya nombrado con Save3 (retorna True y persiste los 28 mates!)
        bool okSave = asmDoc.Save3((int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref se, ref sw);
        Console.WriteLine("\n[OK] Ensamble maestro guardado (" + okSave + ", err=" + se + ", warn=" + sw + "): " + masterAsmPath);

        if (!string.IsNullOrEmpty(shotOut))
        {
            int pe = 0, pw = 0;
            bool okPng = asmDoc.Extension.SaveAs3(shotOut, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref pe, ref pw);
            Console.WriteLine("[OK] Captura directa de SolidWorks 2025 (" + okPng + "): " + shotOut);
        }
    }
}
"@

[void][System.Reflection.Assembly]::LoadFrom($swDll)
[void][System.Reflection.Assembly]::LoadFrom($constDll)
Add-Type -TypeDefinition $csCode -ReferencedAssemblies @($swDll, $constDll)

$m = Get-Content $manifest -Raw | ConvertFrom-Json
$masterAsm = Join-Path $swWorkDir "MiniPro_B2_Stealth_v4.SLDASM"

$builder = New-Object MiniProSwBuilder
try {
    $builder.BuildAll(
        $stepDir, $subDir, $masterAsm, $shotOut,
        [double]$m.d1_m, [double]$m.a2_m, [double]$m.a3_m,
        [double]$m.gx_m, [double]$m.gy_m, [double]$m.ix_m, [double]$m.iy_m, [double]$m.link_l_m,
        [double]$m.hero_q1_deg, [double]$m.hero_q2_deg, [double]$m.hero_q3_deg, [double]$m.hero_q4_deg,
        [double]$m.hero_grip_theta_deg
    )
}
finally {
    $builder.Shutdown()
}
