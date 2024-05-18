using System.Net.Sockets;
using Bungie;
using System.Net;
using System;
using Newtonsoft.Json.Linq;
using System.Text;
using System.IO;
using System.Collections.Generic;
using Newtonsoft.Json;
using System.Threading.Tasks;
using System.Threading;

namespace FoundryBlam
{
    internal class Program
    {

        private static string _latestJsonData = null;
        private static readonly object _lock = new object();
        private static CancellationTokenSource _cts = new CancellationTokenSource();

        static void Main(string[] args)
        {
            bool debug = false;
            string projectPath = args[0];
            bool corinth = bool.TrueString == args[1];
            int port = int.Parse(args[2]);
            ManagedBlamCrashCallback callback = info => { };
            ManagedBlamStartupParameters startupParamaters = new ManagedBlamStartupParameters
            {
                InitializationLevel = InitializationType.TagsOnly
            };
            ManagedBlamSystem.Start(projectPath, callback, startupParamaters);

            if (debug)
            {
                string debugData = """{"function": "BuildScenarioStructureLightingInfo", "path": "foundry_test\\scenarios\\light_sync_test\\light_sync_test_default.scenario_structure_lighting_info", "data": {"instances": [{"DataName": "Point", "Bsp": "default", "Origin": [-0.0773564875125885, 0.630765974521637, 0.6964206695556641], "Forward": [-0.0, 1.0, 0.0], "Up": [0.0, -0.0, 1.0], "GameType": 0, "VolumeDistance": 0.0, "VolumeIntensity": 1.0, "BounceRatio": 1.0, "ScreenSpaceSpecular": false, "LightTag": "", "Shader": "", "Gel": "", "LensFlare": "", "LightMode": 1}], "definitions": [{"DataName": "Point", "Type": 0, "Shape": 1, "Color": [0.9999999999999999, 0.9999999999999999, 0.9999999999999999], "Intensity": 0.9999999999999999, "HotspotSize": 0, "HotspotCutoff": 0, "HotspotFalloff": 1.0, "NearAttenuationStart": 0.0, "NearAttenuationEnd": 0.0, "FarAttenuationStart": 0.0, "FarAttenuationEnd": 0.0, "Aspect": 1.0, "ConeShape": 0, "ShadowNearClip": 0.0, "ShadowFarClip": 0.0, "ShadowBias": 0.0, "ShadowColor": [0.0, 0.0, 0.0], "ShadowQuality": 0, "Shadows": 1, "ScreenSpace": 0, "IgnoreDynamicObjects": 0, "CinemaOnly": 0, "CinemaExclude": 0, "SpecularContribution": 1, "DiffuseContribution": 1, "IndirectAmp": 0.5, "JitterSphere": 0.0, "JitterAngle": 0.0, "JitterQuality": 2, "IndirectOnly": 0, "StaticAnalytic": 0}]}}""";
                JObject debugJson = JObject.Parse(debugData);
                JToken my_data = debugJson["data"];
                BuildScenarioStructureLightingInfo(@"foundry_test\scenarios\light_sync_test\light_sync_test_default.scenario_structure_lighting_info", true, my_data);
                return;
            }

            TcpListener server = new TcpListener(IPAddress.Any, port);
            server.Start();

            TcpClient client = server.AcceptTcpClient();

            NetworkStream stream = client.GetStream();
            StreamReader reader = new StreamReader(stream, Encoding.UTF8);

            Task.Run(() => ReadLatestLine(reader, _cts.Token));

            while (true)
            {
                string jsonData;
                lock (_lock)
                {
                    jsonData = _latestJsonData;
                }

                if (!string.IsNullOrEmpty(jsonData))
                {

                    JObject json = JObject.Parse(jsonData);

                    string functionName = json["function"].ToString();
                    string path = json["path"].ToString();
                    JToken data = json["data"];
                    switch (functionName)
                    {
                        case "BuildScenarioStructureLightingInfo":
                            BuildScenarioStructureLightingInfo(path, corinth, data);
                            break;
                        case "ClearScenarioStructureLightingInfo":
                            ClearScenarioStructureLightingInfo(path, corinth, data);
                            break;
                        default:
                            Console.WriteLine("Unknown function: " + functionName);
                            break;
                    }

                    lock (_lock)
                    {
                        _latestJsonData = null;
                    }

                if (_cts.Token.IsCancellationRequested)
                {
                    break;
                }

                }
            }
            _cts.Cancel();
            client.Close();
            server.Stop();
        }

        private static void ReadLatestLine(StreamReader reader, CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    string line = reader.ReadLine();
                    if (line != null)
                    {
                        lock (_lock)
                        {
                            _latestJsonData = line;
                        }
                    }
                }
                catch (IOException)
                {
                    
                }
            }
        }

        private static void BuildScenarioStructureLightingInfo(string path, bool corinth, JToken data)
        {
            List<LightInstance> lightsInstances = JsonConvert.DeserializeObject<List<LightInstance>>(data["instances"].ToString());
            List<LightDefinition> lightsDefinitions = JsonConvert.DeserializeObject<List<LightDefinition>>(data["definitions"].ToString());
            using (ScenarioStructureLightingInfoTag info = new ScenarioStructureLightingInfoTag(path, corinth))
            {
                info.BuildTag(lightsInstances, lightsDefinitions);
            }
        }

        private static void ClearScenarioStructureLightingInfo(string path, bool corinth, JToken data)
        {
            using (ScenarioStructureLightingInfoTag info = new ScenarioStructureLightingInfoTag(path, corinth))
            {
                info.ClearLights();
            }
        }
    }

}
