// tests/keyboard_test.cpp
#include "quadruped_sdk/udp_client.h"
#include "quadruped_sdk/json_parser.h"
#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <unistd.h>
#include <termios.h>
#include <stdio.h>
#include <atomic>
#include <fcntl.h>
#include <sys/ioctl.h>

using namespace quadruped_sdk;

// 获取键盘输入（非阻塞）
char getch_noblock() {
    struct termios oldt, newt;
    char ch;
    int oldf;

    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);
    oldf = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);

    ch = getchar();

    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    fcntl(STDIN_FILENO, F_SETFL, oldf);

    return ch;
}

class KeyboardController {
private:
    JsonParser& parser_;
    std::atomic<bool> running_{false};
    std::thread control_thread_;
    
    // 控制状态
    std::atomic<int> current_direction_{0};  // 0=停止, 1=前后, 2=左右, 3=旋转
    std::atomic<double> current_velocity_{0.0};
    std::atomic<bool> need_send_command_{false};
    
    // 上次发送时间
    std::chrono::steady_clock::time_point last_send_time_;
    
public:
    KeyboardController(JsonParser& parser) : parser_(parser) {}
    
    ~KeyboardController() {
        stop();
    }
    
    void start() {
        if (running_) return;
        
        running_ = true;
        control_thread_ = std::thread(&KeyboardController::controlLoop, this);
        std::cout << "键盘控制器已启动" << std::endl;
    }
    
    void stop() {
        if (!running_) return;
        
        running_ = false;
        if (control_thread_.joinable()) {
            control_thread_.join();
        }
        std::cout << "键盘控制器已停止" << std::endl;
    }
    
    // 设置运动命令
    void setMotion(int direction, double velocity) {
        current_direction_ = direction;
        current_velocity_ = velocity;
        need_send_command_ = true;
        last_send_time_ = std::chrono::steady_clock::now();
    }
    
    // 停止所有运动
    void stopMotion() {
        current_direction_ = 0;
        current_velocity_ = 0.0;
        need_send_command_ = true;
    }
    
    // 获取当前速度
    double getCurrentVelocity() const {
        return current_velocity_;
    }
    
    // 获取当前方向
    int getCurrentDirection() const {
        return current_direction_;
    }
    
private:
    void controlLoop() {
        const int send_interval_ms = 50;  // 20Hz发送频率
        
        while (running_) {
            // 检查是否需要发送速度命令
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                now - last_send_time_).count();
            
            // 如果超过100ms没有发送命令，发送零速度
            if (elapsed > 100 && current_direction_ != 0) {
                // std::cout << "自动发送零速度" << std::endl;
                parser_.sendDirectionVel(0, 0, 0);
                current_direction_ = 0;
                current_velocity_ = 0.0;
            }
            
            // 如果需要发送命令
            if (need_send_command_) {
                if (current_direction_ > 0) {
                    parser_.sendDirectionVel(current_direction_, current_velocity_);
                } else {
                    parser_.sendDirectionVel(0, 0, 0);
                }
                need_send_command_ = false;
                last_send_time_ = now;
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(send_interval_ms));
        }
        
        // 退出时发送零速度
        parser_.sendDirectionVel(0, 0, 0);
    }
};

void printMenu(double velocity) {
    system("clear");  // 清屏
    std::cout << "\n=== 机器狗键盘控制测试 ===" << std::endl;
    std::cout << "  r     - 复位回零" << std::endl;
    std::cout << "  w/s   - 前进/后退" << std::endl;
    std::cout << "  a/d   - 左移/右移" << std::endl;
    std::cout << "  q/e   - 左转/右转" << std::endl;
    std::cout << "  t     - 急停" << std::endl;
    std::cout << "  y     - 站起" << std::endl;
    std::cout << "  u     - 趴下" << std::endl;
    std::cout << "  i     - 切换模型" << std::endl;
    std::cout << "  o     - 打开/关闭停障设置" << std::endl;
    std::cout << "  +     - 增加速度" << std::endl;
    std::cout << "  -     - 减少速度" << std::endl;
    std::cout << "  x     - 停止所有运动" << std::endl;
    std::cout << "  h     - 显示帮助" << std::endl;
    std::cout << "  ESC   - 退出程序" << std::endl;
    std::cout << "当前速度: " << velocity << std::endl;
    std::cout << "===========================\n" << std::endl;
}

int main(int argc, char* argv[]) {
    // 解析命令行参数
    std::string server_ip = "192.168.96.2";
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
    
    std::cout << "=== 键盘控制客户端已启动 ===" << std::endl;
    std::cout << "目标服务器: " << server_ip << ":" << server_port << std::endl;

    // 测试连接
    if (!client.testConnection()) {
        std::cerr << "无法连接到服务器" << std::endl;
        return 1;
    }

    // 创建JsonParser
    JsonParser parser(std::move(client));
    
    // 启动解析器（在后台线程运行）
    parser.run();
    
    // 等待JsonParser启动
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // 创建键盘控制器
    KeyboardController controller(parser);
    controller.start();
    
    double velocity = 0.5;
    bool running = true;
    
    printMenu(velocity);

    while (running) {
        char key = getch_noblock();
        
        static bool currentMode = true;
        static bool isObstacleOpen = true;
        if (key != EOF) {  // 有按键输入
            switch (key) {
                case 'w':  // 前进
                    std::cout << "前进: 速度 " << velocity << std::endl;
                    controller.setMotion(1, velocity);  // 1=前后方向，正速度
                    break;
                    
                case 's':  // 后退
                    std::cout << "后退: 速度 " << velocity << std::endl;
                    controller.setMotion(1, -velocity);  // 1=前后方向，负速度
                    break;
                    
                case 'a':  // 左移
                    std::cout << "左移: 速度 " << velocity << std::endl;
                    controller.setMotion(2, velocity);  // 2=左右方向，正速度
                    break;
                    
                case 'd':  // 右移
                    std::cout << "右移: 速度 " << velocity << std::endl;
                    controller.setMotion(2, -velocity);  // 2=左右方向，负速度
                    break;
                    
                case 'q':  // 左转
                    std::cout << "左转: 速度 " << velocity << std::endl;
                    controller.setMotion(3, velocity);  // 3=旋转方向，正速度
                    break;
                    
                case 'e':  // 右转
                    std::cout << "右转: 速度 " << velocity << std::endl;
                    controller.setMotion(3, -velocity);  // 3=旋转方向，负速度
                    break;
                    
                case 'r':  // 复位
                    std::cout << "发送复位命令..." << std::endl;
                    controller.stopMotion();  // 先停止运动
                    parser.handleResetCommand();
                    break;
                    
                case 't':  // 急停
                    std::cout << "发送急停命令..." << std::endl;
                    controller.stopMotion();  // 先停止运动
                    parser.handleEmergencyCommand();
                    break;
                    
                case 'y':  // 站起
                    std::cout << "发送站起命令..." << std::endl;
                    controller.stopMotion();  // 先停止运动
                    parser.handleStandUpCommand();
                    break;
                    
                case 'u':  // 趴下
                    std::cout << "发送趴下命令..." << std::endl;
                    controller.stopMotion();  // 先停止运动
                    parser.handleLieDownCommand();
                    break;

                case 'o':
                    controller.stopMotion();  // 先停止运动
                    if(currentMode){
                        if(isObstacleOpen){
                            std::cout << "发送关闭停障命令..." << std::endl;
                            parser.handleLidarObstacleCommand(0);
                            isObstacleOpen = false;
                        }else{
                            std::cout << "发送开启停障命令..." << std::endl;
                            parser.handleLidarObstacleCommand(1);
                            isObstacleOpen = true;
                        }
                    }
                    break;
                    
                case 'i':  // 切换模型
                    controller.stopMotion();  // 先停止运动
                    if(!currentMode){
                        std::cout << "发送切换高速模型命令..." << std::endl;
                        parser.handleSwitchMnnCommand(1);
                        currentMode = true;
                    }else{
                        std::cout << "发送切换越障模型命令..." << std::endl;
                        parser.handleSwitchMnnCommand(0);
                        currentMode = false;
                    }
                    
                    break;
                    
                case '+':  // 增加速度
                    velocity = std::min(1.0, velocity + 0.1);
                    std::cout << "速度增加至: " << velocity << std::endl;
                    // 如果当前正在运动，更新速度
                    if (controller.getCurrentDirection() > 0) {
                        controller.setMotion(controller.getCurrentDirection(), 
                                           controller.getCurrentVelocity() > 0 ? velocity : -velocity);
                    }
                    printMenu(velocity);
                    break;
                    
                case '-':  // 减少速度
                    velocity = std::max(0.1, velocity - 0.1);
                    std::cout << "速度减少至: " << velocity << std::endl;
                    // 如果当前正在运动，更新速度
                    if (controller.getCurrentDirection() > 0) {
                        controller.setMotion(controller.getCurrentDirection(), 
                                           controller.getCurrentVelocity() > 0 ? velocity : -velocity);
                    }
                    printMenu(velocity);
                    break;
                    
                case 'x':  // 停止
                    std::cout << "停止所有运动" << std::endl;
                    controller.stopMotion();
                    break;
                    
                case 'h':  // 帮助
                    printMenu(velocity);
                    break;
                    
                case 27:  // ESC键
                    std::cout << "退出程序..." << std::endl;
                    running = false;
                    break;
                    
                default:
                    if (key != '\n') {  // 忽略回车键
                        //std::cout << "未知按键: " << key << " (按h查看帮助)" << std::endl;
                    }
                    break;
            }
        }
        
        // 短暂延迟，减少CPU占用
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // 停止控制器
    controller.stop();
    
    // 确保发送最后一次零速度
    parser.sendDirectionVel(0, 0, 0);
    
    // 停止JsonParser
    parser.stop();
    
    std::cout << "程序结束" << std::endl;
    
    return 0;
}