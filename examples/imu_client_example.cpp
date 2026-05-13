// examples/imu_client_example.cpp
#include "quadruped_sdk/udp_client.h"
#include "quadruped_sdk/json_parser.h"
#include "quadruped_sdk/imu_data.h"
#include <iostream>
#include <thread>
#include <chrono>
#include <iomanip>
#include <atomic>
#include <csignal>
#include <cmath>      // 添加这个头文件用于数学函数

// 如果M_PI未定义，手动定义它
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

std::atomic<bool> running(true);

void signalHandler(int signum) {
    std::cout << "\nInterrupt signal received, exiting..." << std::endl;
    running = false;
}

// IMU数据回调函数
void imuDataCallback(const quadruped_sdk::IMUData& imu_data) {
    static int count = 0;
    
    // 每10次显示一次
    if (count++ % 10 == 0) {
        auto euler = imu_data.getEulerAngles();
        
        std::cout << "\rIMU Data - "
                 << "Time: " << std::fixed << std::setprecision(3) << imu_data.ros_timestamp
                 << " | Accel: (" 
                 << std::setw(6) << std::setprecision(2) << imu_data.linear_acceleration.x
                 << ", " << std::setw(6) << imu_data.linear_acceleration.y
                 << ", " << std::setw(6) << imu_data.linear_acceleration.z << ") m/s²"
                 << " | Gyro: (" 
                 << std::setw(6) << std::setprecision(2) << imu_data.angular_velocity.x
                 << ", " << std::setw(6) << imu_data.angular_velocity.y
                 << ", " << std::setw(6) << imu_data.angular_velocity.z << ") rad/s"
                 << " | RPY: (" 
                 << std::setw(6) << std::setprecision(1) << euler.roll * 180.0 / M_PI
                 << ", " << std::setw(6) << euler.pitch * 180.0 / M_PI
                 << ", " << std::setw(6) << euler.yaw * 180.0 / M_PI << ") deg"
                 << std::flush;
    }
}

void printIMUStatistics(const quadruped_sdk::IMUData& imu_data) {
    auto euler = imu_data.getEulerAngles();
    
    std::cout << "\n=== IMU Statistics ===" << std::endl;
    std::cout << "Frame ID: " << imu_data.frame_id << std::endl;
    std::cout << "Timestamp: " << std::fixed << std::setprecision(6) 
              << imu_data.ros_timestamp << " s" << std::endl;
    
    std::cout << "\nLinear Acceleration:" << std::endl;
    std::cout << "  X: " << std::setw(8) << std::setprecision(4) 
              << imu_data.linear_acceleration.x << " m/s²" << std::endl;
    std::cout << "  Y: " << std::setw(8) << imu_data.linear_acceleration.y << " m/s²" << std::endl;
    std::cout << "  Z: " << std::setw(8) << imu_data.linear_acceleration.z << " m/s²" << std::endl;
    
    std::cout << "\nAngular Velocity:" << std::endl;
    std::cout << "  X: " << std::setw(8) << std::setprecision(4) 
              << imu_data.angular_velocity.x << " rad/s" << std::endl;
    std::cout << "  Y: " << std::setw(8) << imu_data.angular_velocity.y << " rad/s" << std::endl;
    std::cout << "  Z: " << std::setw(8) << imu_data.angular_velocity.z << " rad/s" << std::endl;
    
    std::cout << "\nOrientation (Quaternion):" << std::endl;
    std::cout << "  W: " << std::setw(8) << std::setprecision(4) 
              << imu_data.orientation.w << std::endl;
    std::cout << "  X: " << std::setw(8) << imu_data.orientation.x << std::endl;
    std::cout << "  Y: " << std::setw(8) << imu_data.orientation.y << std::endl;
    std::cout << "  Z: " << std::setw(8) << imu_data.orientation.z << std::endl;
    
    std::cout << "\nEuler Angles:" << std::endl;
    std::cout << "  Roll:  " << std::setw(8) << std::setprecision(2) 
              << euler.roll * 180.0 / M_PI << " °" << std::endl;
    std::cout << "  Pitch: " << std::setw(8) << euler.pitch * 180.0 / M_PI << " °" << std::endl;
    std::cout << "  Yaw:   " << std::setw(8) << euler.yaw * 180.0 / M_PI << " °" << std::endl;
    
    // 计算加速度大小
    double accel_magnitude = sqrt(
        imu_data.linear_acceleration.x * imu_data.linear_acceleration.x +
        imu_data.linear_acceleration.y * imu_data.linear_acceleration.y +
        imu_data.linear_acceleration.z * imu_data.linear_acceleration.z);
    
    // 计算角速度大小
    double gyro_magnitude = sqrt(
        imu_data.angular_velocity.x * imu_data.angular_velocity.x +
        imu_data.angular_velocity.y * imu_data.angular_velocity.y +
        imu_data.angular_velocity.z * imu_data.angular_velocity.z);
    
    std::cout << "\nMagnitudes:" << std::endl;
    std::cout << "  Acceleration: " << std::setw(8) << std::setprecision(3) 
              << accel_magnitude << " m/s²" << std::endl;
    std::cout << "  Angular Vel:  " << std::setw(8) << gyro_magnitude << " rad/s" << std::endl;
    
    std::cout << "========================\n" << std::endl;
}

int main(int argc, char* argv[]) {
    // 注册信号处理
    std::signal(SIGINT, signalHandler);
    
    std::string server_ip = "192.168.96.2"; // 127.0.0.1
    int server_port = 8080;
    
    if (argc >= 3) {
        server_ip = argv[1];
        server_port = std::stoi(argv[2]);
    }
    
    std::cout << "=== IMU Client Example ===" << std::endl;
    std::cout << "Server: " << server_ip << ":" << server_port << std::endl;
    std::cout << "Press Ctrl+C to exit\n" << std::endl;
    
    // 创建UDP客户端
    quadruped_sdk::UDPClient client(server_ip, server_port);
    
    if (!client.initialize()) {
        std::cerr << "Failed to initialize UDP client" << std::endl;
        return 1;
    }
    
    if (!client.testConnection()) {
        std::cerr << "Cannot connect to server" << std::endl;
        return 1;
    }
    
    // 创建JsonParser
    quadruped_sdk::JsonParser parser(std::move(client));
    
    // 设置IMU数据回调
    parser.setIMUDataCallback(imuDataCallback);
    
    // 启动解析器
    parser.run();
    
    // 等待连接稳定
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // 启用IMU数据流
    if (!parser.enableIMUStream()) {
        std::cerr << "Failed to enable IMU stream" << std::endl;
        parser.stop();
        return 1;
    }
    
    std::cout << "IMU stream enabled, waiting for data..." << std::endl;
    
    // 主循环
    int display_counter = 0;
    while (running) {
        // 定期显示详细统计信息
        if (display_counter++ % 200 == 0) {  // 每2秒显示一次
            auto imu_data = parser.getLatestIMUData();
            printIMUStatistics(imu_data);
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    
    // 清理
    std::cout << "\nDisabling IMU stream..." << std::endl;
    parser.disableIMUStream();
    
    std::cout << "Stopping parser..." << std::endl;
    parser.stop();
    
    std::cout << "IMU client example finished" << std::endl;
    
    return 0;
}