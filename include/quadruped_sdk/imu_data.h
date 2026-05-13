// include/quadruped_sdk/imu_data.h
#pragma once

#include <chrono>
#include <vector>
#include <string>

namespace quadruped_sdk {

struct IMUData {
    // 时间戳
    std::chrono::system_clock::time_point timestamp;
    double ros_timestamp;  // ROS时间戳（秒）
    std::string frame_id;
    
    // 线性加速度 (m/s²)
    struct LinearAcceleration {
        float x, y, z;
        LinearAcceleration() : x(0), y(0), z(0) {}
    } linear_acceleration;
    
    // 角速度 (rad/s)
    struct AngularVelocity {
        float x, y, z;
        AngularVelocity() : x(0), y(0), z(0) {}
    } angular_velocity;
    
    // 四元数姿态
    struct Orientation {
        float w, x, y, z;
        Orientation() : w(1), x(0), y(0), z(0) {}
    } orientation;
    
    // 协方差矩阵
    std::vector<double> orientation_covariance;
    std::vector<double> angular_velocity_covariance;
    std::vector<double> linear_acceleration_covariance;
    
    // 计算欧拉角（可选）
    struct EulerAngles {
        float roll, pitch, yaw;  // 弧度
        EulerAngles() : roll(0), pitch(0), yaw(0) {}
    };
    
    EulerAngles getEulerAngles() const;
    
    IMUData();
};

} // namespace quadruped_sdk