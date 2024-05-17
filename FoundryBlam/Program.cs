using System.Net.Sockets;
using Bungie;
using Bungie.Tags;
using System.Net;
using System;
using Newtonsoft.Json.Linq;
using System.Text;
using System.IO;
using System.Collections.Generic;
using Newtonsoft.Json;
using System.Runtime.InteropServices;
using System.Linq;
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
            // Load ManagedBlam
            if (args.Length <= 0)
            {
                Console.WriteLine("No project path specified");
                return;
            }

            if (args.Length <= 1)
            {
                Console.WriteLine("No port specified");
                return;
            }

            string projectPath = args[0];
            int port = int.Parse(args[1]);
            ManagedBlamCrashCallback callback = info => { };
            ManagedBlamStartupParameters startupParamaters = new ManagedBlamStartupParameters
            {
                InitializationLevel = InitializationType.TagsOnly
            };
            ManagedBlamSystem.Start(projectPath, callback, startupParamaters);

            // Setup up listener
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

                //if (jsonData == null)
                //    break;

                if (!string.IsNullOrEmpty(jsonData))
                {

                    JObject json = JObject.Parse(jsonData);

                    string functionName = json["function"].ToString();
                    string path = json["path"].ToString();
                    JToken data = json["data"];
                    switch (functionName)
                    {
                        case "BuildScenarioStructureLightingInfo":
                            BuildScenarioStructureLightingInfo(path, data);
                            break;
                        // Add more cases for other function names as needed
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

        private static void BuildScenarioStructureLightingInfo(string path, JToken data)
        {
            List<LightInstance> lightsInstances = JsonConvert.DeserializeObject<List<LightInstance>>(data["instances"].ToString());
            List<LightDefinition> lightsDefinitions = JsonConvert.DeserializeObject<List<LightDefinition>>(data["definitions"].ToString());
            using (ScenarioStructureLightingInfoTag info = new ScenarioStructureLightingInfoTag(path))
            {
                info.BuildTag(lightsInstances, lightsDefinitions);
            }
        }
    }

}
