// src/imu_data.cpp
#include "quadruped_sdk/imu_data.h"
#include <cmath>

namespace quadruped_sdk {

IMUData::IMUData() {
    timestamp = std::chrono::system_clock::now();
    ros_timestamp = 0.0;
    
    // 初始化协方差矩阵（9个元素）
    orientation_covariance.resize(9, 0.0);
    angular_velocity_covariance.resize(9, 0.0);
    linear_acceleration_covariance.resize(9, 0.0);
    
    // 设置默认协方差（表示数据可靠）
    orientation_covariance[0] = 0.01;  // xx
    orientation_covariance[4] = 0.01;  // yy
    orientation_covariance[8] = 0.01;  // zz
}

IMUData::EulerAngles IMUData::getEulerAngles() const {
    EulerAngles euler;
    
    // 从四元数计算欧拉角
    // roll (x-axis rotation)
    double sinr_cosp = 2 * (orientation.w * orientation.x + orientation.y * orientation.z);
    double cosr_cosp = 1 - 2 * (orientation.x * orientation.x + orientation.y * orientation.y);
    euler.roll = std::atan2(sinr_cosp, cosr_cosp);
    
    // pitch (y-axis rotation)
    double sinp = 2 * (orientation.w * orientation.y - orientation.z * orientation.x);
    if (std::abs(sinp) >= 1)
        euler.pitch = std::copysign(M_PI / 2, sinp);  // 使用90度
    else
        euler.pitch = std::asin(sinp);
    
    // yaw (z-axis rotation)
    double siny_cosp = 2 * (orientation.w * orientation.z + orientation.x * orientation.y);
    double cosy_cosp = 1 - 2 * (orientation.y * orientation.y + orientation.z * orientation.z);
    euler.yaw = std::atan2(siny_cosp, cosy_cosp);
    
    return euler;
}

} // namespace quadruped_sdk