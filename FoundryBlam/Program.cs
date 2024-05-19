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
            string projectPath = args[0];
            int port = int.Parse(args[1]);
            ManagedBlamCrashCallback callback = info => { };
            ManagedBlamStartupParameters startupParamaters = new ManagedBlamStartupParameters
            {
                InitializationLevel = InitializationType.TagsOnly
            };
            ManagedBlamSystem.Start(projectPath, callback, startupParamaters);

            TcpListener server = new TcpListener(IPAddress.Any, port);
            server.Start();

            TcpClient client = server.AcceptTcpClient();

            NetworkStream stream = client.GetStream();
            StreamReader reader = new StreamReader(stream, Encoding.UTF8);

            Task.Run(() => ReadLatestLine(reader, _cts.Token));

            while (!_cts.Token.IsCancellationRequested)
            {
                string jsonData;
                lock (_lock)
                {
                    jsonData = _latestJsonData;
                }

                if (!string.IsNullOrEmpty(jsonData))
                {
                    JArray jsonArray = JArray.Parse(jsonData);
                    foreach (JObject jsonObject in jsonArray)
                    {
                        string functionName = jsonObject["function"].ToString();
                        string path = jsonObject["path"].ToString();
                        JToken data = jsonObject["data"];
                        switch (functionName)
                        {
                            case "BuildScenarioStructureLightingInfo":
                                BuildScenarioStructureLightingInfo(path, data);
                                break;
                            case "ClearScenarioStructureLightingInfo":
                                ClearScenarioStructureLightingInfo(path, data);
                                break;
                            case "WritePrefabs":
                                WritePrefabs(path, data);
                                break;
                            default:
                                Console.WriteLine("Unknown function: " + functionName);
                                break;
                        }
                    }

                    lock (_lock)
                    {
                        _latestJsonData = null;
                    }

                }

                Thread.Sleep(100);
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

        private static void BuildScenarioStructureLightingInfo(string path, JToken data)
        {
            List<LightInstance> lightsInstances = JsonConvert.DeserializeObject<List<LightInstance>>(data["instances"].ToString());
            List<LightDefinition> lightsDefinitions = JsonConvert.DeserializeObject<List<LightDefinition>>(data["definitions"].ToString());
            using (ScenarioStructureLightingInfoTag info = new ScenarioStructureLightingInfoTag(path))
            {
                info.BuildTag(lightsInstances, lightsDefinitions);
            }
        }

        private static void ClearScenarioStructureLightingInfo(string path, JToken data)
        {
            using (ScenarioStructureLightingInfoTag info = new ScenarioStructureLightingInfoTag(path))
            {
                info.ClearLights();
            }
        }
        private static void WritePrefabs(string path, JToken data)
        {
            List<Prefab> prefabs = JsonConvert.DeserializeObject<List<Prefab>>(data["prefabs"].ToString());
            using (ScenarioStructureBspTag bsp = new ScenarioStructureBspTag(path))
            {
                bsp.WritePrefabs(prefabs);
            }
        }
    }

}
