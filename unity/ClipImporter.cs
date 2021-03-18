using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;

public class ClipImporter : AssetPostprocessor
{
    static ModelImporter currentFBX;
    static string[] currentCSV;
    static string currentCSVpath;

    void OnPreprocessAsset()
    {
        if(assetPath.Contains(".fbx"))
        {
            currentFBX = assetImporter as ModelImporter;
            return;
        }

        if(assetPath.Contains(".csv"))
        {
            currentCSVpath = assetPath;
            string fileData = System.IO.File.ReadAllText(assetPath);
            string[] lines = fileData.Split("\n"[0]);

            List<string> dataList = new List<string>();
            for (int i = 0; i < lines.Length; i++)
            {
                string[] lineData = (lines[i].Trim()).Split(";"[0]);
                foreach(string str in lineData)
                {
                    if (str != "")
                    {
                        dataList.Add(str);
                    }
                }
            }

            currentCSV = dataList.ToArray();
            return;
        }
        
    }

    static void OnPostprocessAllAssets(string[] importedAssets, string[] deletedAssets, string[] movedAssets, string[] movedFromAssetPaths)
    {
        if(currentFBX != null && currentCSV != null && importedAssets.Length == 2)
        {
            Debug.Log("FBX file has a CSV counterpart. Creating Animations...");
            if(currentCSV.Length % 3 != 0)
            {
                Debug.LogWarning("Invalid .CSV file, current length is " + currentCSV.Length.ToString());
                return;
            }

            int animationCount = currentCSV.Length / 3;
            Debug.Log("Parsing animations, " + animationCount.ToString() + " clips found.");
            ModelImporterClipAnimation[] anim = new ModelImporterClipAnimation[animationCount];
            for (int i = 0; i < animationCount; i++)
            {
                int index = i * 3;
                anim[i] = new ModelImporterClipAnimation();
                anim[i].name = currentCSV[index];
                anim[i].firstFrame = float.Parse(currentCSV[index + 1]);
                anim[i].lastFrame = float.Parse(currentCSV[index + 2]);
            }

            currentFBX.clipAnimations = anim;
            FileUtil.DeleteFileOrDirectory(currentCSVpath);
        }
        
        currentFBX = null;
        currentCSV = null;
        currentCSVpath = null;
    }
}
