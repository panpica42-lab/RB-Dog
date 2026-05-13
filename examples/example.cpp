#include "quadruped_sdk/udp_client.h"
#include "quadruped_sdk/json_parser.h"
#include <iostream>
#include <string>
#include <cstdlib>
#include <unistd.h>
#include <iostream>
#include <thread>
#include <chrono>
#include <thread>

using namespace quadruped_sdk;

enum Direction{
    move_front_back = 1,
    move_left_right,
    turn_left_right,
};

double velocity = 0.5;

int main(int argc, char* argv[]) {
    // 解析命令行参数
    std::string server_ip = "192.168.96.2"; //127.0.0.1  192.168.96.2
    int server_port = 8080;
    
    if (argc >= 3) {
        server_ip = argv[1];
        server_port = std::stoi(argv[2]);
    }
    
    // 创建UDP客户端
    UDPClient client(server_ip, server_port);
    
    // 初始化客户端
    if (!client.initialize()) {
        std::cerr << "客户端初始化失败" << std::endl;
        return 1;
    }
    
    std::cout << "=== UDP客户端已启动 ===" << std::endl;
    std::cout << "目标服务器: " << client.getServerInfo() << std::endl;

    bool isConnect = client.testConnection();
    if(isConnect)
    {
        // 1. 创建JsonParser（使用移动构造）
        JsonParser parser(std::move(client));
        parser.run();

        int mode = 0;
        auto start = std::chrono::steady_clock::now();
        bool is_break = false;

        while(!is_break){
            // 获取机器狗实时状态
            DogStatus status = parser.getDogStatus();

            switch(mode){
                case 0:
                    {
                        if(status.motion_mode == MODE_LYING_DOWN_WITHOUT_RESET)
                        {
                            mode = 1;
                        }
                    }
                    break;
                case 1:
                    parser.handleResetCommand(); // 机器狗复位回零
                    mode = 2;
                    std::cout << "=== change mode to Reset ===" << std::endl;
                    break;
                case 2:
                    if(status.motion_mode == MODE_STANDING) // 等待机器狗复位完成  MODE_STANDING
                    {
                        mode = 3;
                        start = std::chrono::steady_clock::now();
                        std::cout << "=== change mode to forward ===" << std::endl;
                    }
                    break;
                case 3:
                    {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 4;
                            std::cout << "=== change mode to backward ===" << std::endl;
                        }
                        else if(duration_s <= 1.0){
                            // 给机器狗向前速度 0.5  range: 0-1.0
                            parser.sendDirectionVel(move_front_back,velocity); 
                            // parser.sendDirectionVel(velocity, 0, 0); 
                        }
                        else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 4:
                    {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 5;
                            std::cout << "=== change mode to move_left ===" << std::endl;
                        }else if(duration_s <= 1.0){
                            // 给机器狗向后速度 -0.5  range: -1.0-0
                            parser.sendDirectionVel(move_front_back,-velocity); 
                            // parser.sendDirectionVel(velocity, 0, 0); 
                        }else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 5:
                    {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 6;
                            std::cout << "=== change mode to move_right ===" << std::endl;
                        }else if(duration_s <= 1.0){
                            // 给机器狗向左速度 0.5 range: 0-1.0
                            parser.sendDirectionVel(move_left_right,velocity); 
                            // parser.sendDirectionVel(0, velocity, 0);
                        }else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 6:
                    {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 7;
                            std::cout << "=== change mode to turn_left ===" << std::endl;
                        }else if(duration_s <= 1.0){
                            // 给机器狗向右速度 -0.5 range: -1.0-0
                            parser.sendDirectionVel(move_left_right,-velocity);
                            // parser.sendDirectionVel(0, -velocity, 0);
                        }else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 7:
                    {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 8;
                            std::cout << "=== change mode to turn_right ===" << std::endl;
                        }else if(duration_s <= 1.0){
                            // 给机器狗左转速度 0.5 range: 0-1.0
                            parser.sendDirectionVel(turn_left_right,velocity);
                            // parser.sendDirectionVel(0, 0, velocity);
                        }else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 8:
                     {
                        auto end = std::chrono::steady_clock::now();
                        auto duration_s = std::chrono::duration<double>(end - start).count();
                        if(duration_s > 2.0){
                            start = std::chrono::steady_clock::now();
                            mode = 9;
                            std::cout << "=== change mode to Lie Down ===" << std::endl;
                        }else if(duration_s <= 1.0){
                            // 给机器狗右转速度 -0.5 range: -1.0-0
                            parser.sendDirectionVel(turn_left_right,-velocity);
                            // parser.sendDirectionVel(0, 0, -velocity);
                        }else if(duration_s > 1.0){
                            parser.sendDirectionVel(0, 0, 0);
                        }
                    }
                    break;
                case 9:
                    {
                        // lie down
                        parser.handleLieDownCommand();
                        start = std::chrono::steady_clock::now();
                        mode = 10;
                        std::cout << "=== change mode to 10 ===" << std::endl;
                    }
                    break;
                case 10:
                    is_break = true;
                    break;
                default:
                    break;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        
        // parser.run();
    }
    
    return 0;
}