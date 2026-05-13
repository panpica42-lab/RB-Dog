#ifndef QUADRUPED_SDK_JSON_PARSER_H
#define QUADRUPED_SDK_JSON_PARSER_H

#include <string>
#include <jsoncpp/json/json.h>
#include "udp_client.h"
#include <memory>
#include <atomic>
#include <unistd.h>
#include <mutex>
#include <thread>
#include <chrono>
#include "quadruped_sdk/imu_data.h"
#include <functional>

namespace quadruped_sdk {

// 消息类型
enum MessageType {
    MSG_QUERY_REQUEST = 1,
    MSG_QUERY_RESPONSE = 2,
    MSG_COMMAND_REQUEST = 3,
    MSG_COMMAND_RESPONSE = 4,
    MSG_IMUDATA_RESPONSE = 5
};

// 查询代码
enum QueryCode {
    QUERY_REALTIME_STATUS = 1,
    QUERY_BATTERY = 2,
    QUERY_HARDWARE_DETAIL = 3,
    QUERY_HARDWARE_SUMMARY = 4,
    QUERY_PROTOCOL_VERSION = 5,
    QUERY_ROBOT_NUMBER = 6,
    QUERY_SOFTWARE_VERSION = 7,
    QUERY_LATEST_SOFTWARE_VERSION = 8,
    QUERY_ROBOT_TYPE = 9,
    QUERY_MOTION_MODEL = 10
};

// 命令代码
enum CommandCode {
    CMD_SET_VELOCITY_LEVEL = 1,
    CMD_SET_MOTION_MODE = 2,
    CMD_PERFORM_ACTION = 3,
    CMD_RESET = 4,
    CMD_ULTRASONIC_OBSTACLE_AVOIDANCE = 5,
    CMD_EMERGENCY_STOP = 6,
    CMD_UPDATE_SOFTWARE = 7,
    CMD_RECOVER_FROM_FALL = 8,
    CMD_CAMERA_STREAM = 9,
    CMD_STAND_UP = 10,
    CMD_LIE_DOWN = 11,
};

// 运动模式
enum MotionMode {
    MODE_LYING_DOWN_WITHOUT_RESET = 0,
    MODE_LYING_DOWN = 1,
    MODE_STANDING = 2,
    MODE_LOW_POSTURE = 3,
    MODE_FALLEN = 4
};

// 速度档位
enum VelocityLevel {
    VELOCITY_LOW = 1,
    VELOCITY_MEDIUM = 2,
    VELOCITY_HIGH = 3
};

// 机器狗状态数据
struct DogStatus {
    int battery_level = 80;
    int motion_mode = MODE_LYING_DOWN_WITHOUT_RESET;
    int velocity_level = VELOCITY_MEDIUM;
    int model = 0;
    int hardware_error = 0;
    std::vector<int> hw_failures;
    std::string robot_number = "AI15000A";
    double protocol_version = 1.0;
    float software_version = 0.230000;
    float latest_software_version = 0.240000;
    std::string robot_type = "Quadruped";
};

class JsonParser {
private:
    UDPClient client_;           // UDP客户端（移动构造）
    Json::Value root_;           // JSON根节点
    std::string last_error_;     // 最后错误信息
    std::atomic<bool> break_flag{false}; // 线程退出标志（原子变量）
    DogStatus current_status_;       // 缓存机器狗当前状态
    std::string incomplete_msg_; // 新增：暂存不完整的UDP消息
    mutable std::mutex status_mutex_;
    
    int velocity_level = VELOCITY_MEDIUM;

    // 新增：线程相关成员
    std::thread recv_thread_;    // 接收数据的后台线程
    std::mutex mutex_;           // 保护共享数据的互斥锁
    // std::condition_variable cv_; // 条件变量（可选，用于线程唤醒）

    std::thread send_thread_;    // 发送数据的后台线程
    std::mutex send_mutex_;           // 保护共享数据的互斥锁

    bool currentMode = false;

    // IMU数据回调函数类型
    using IMUDataCallback = std::function<void(const IMUData&)>;
    
    // IMU相关成员
    IMUData latest_imu_;
    mutable std::mutex imu_mutex_;
    IMUDataCallback imu_callback_;
    std::atomic<bool> imu_stream_enabled_{false};

    // 新增：私有线程函数——持续接收UDP数据
    void receiveLoop();
    void sendLoop();

    // 新增：响应处理函数（私有，内部分发
    void handleQueryResponse(const Json::Value& response);
    void handleCommandResponse(const Json::Value& response);

public:
    // 构造函数 - 使用移动语义
    explicit JsonParser(UDPClient&& client);
    ~JsonParser();
    
    // 移动构造函数
    JsonParser(JsonParser&& other) noexcept;
    
    // 禁止拷贝构造
    JsonParser(const JsonParser&) = delete;
    JsonParser& operator=(const JsonParser&) = delete;
    
    // 移动赋值运算符
    JsonParser& operator=(JsonParser&& other) noexcept;

    // 核心控制
    void run();   // 启动后台接收线程
    void stop();  // 停止线程并释放资源
    
    // 解析JSON字符串
    bool parseJsonString(const std::string& json_str);
    
    // 从UDP接收并解析JSON
    bool receiveAndParse(int timeout_seconds = 5);
    
    // 发送JSON到UDP服务器
    bool sendJson(const Json::Value& json_value);

    void parseRealtimeStatus(const Json::Value& json_value);
    
    // 发送并接收JSON
    bool sendAndReceiveJson(const Json::Value& request, Json::Value& response, int timeout_seconds = 5);
    
    // 获取JSON值
    Json::Value& getJson() { return root_; }
    const Json::Value& getJson() const { return root_; }
    
    // 获取UDP客户端
    UDPClient& getClient() { return client_; }
    const UDPClient& getClient() const { return client_; }
    
    // 错误处理
    std::string getLastError() const { return last_error_; }
    void clearError() { last_error_.clear(); }
    
    // 便捷方法
    static Json::Value createObject();
    static Json::Value createArray();

    // send wakling direction speed 
    void sendDirectionVel(int direction,double velocity);

    // All direction fuction
    void sendDirectionVel(double move_frontback, double move_leftright, double turn_leftright);

    // change mode 
    void handleSwitchMnnCommand(int mode);

    // handle motion 
    void handleMotionCommand(int para);

    // reset command
    void handleResetCommand();

    // open/close ultrasonic obstacle 
    void handleLidarObstacleCommand(int para);

    // Emergency stop
    void handleEmergencyCommand();

    // stand up
    void handleStandUpCommand();
    
    // lie down command
    void handleLieDownCommand();

    DogStatus getDogStatus() const;

    // 设置IMU数据回调
    void setIMUDataCallback(IMUDataCallback callback);
    
    // 注册/注销IMU数据流
    bool enableIMUStream();
    bool disableIMUStream();
    
    // 获取IMU数据
    IMUData getLatestIMUData() const;

private:
    std::string extract_complete_json(std::string& buffer);

    // 处理IMU消息
    void handleIMUMessage(const Json::Value& json_data);
    bool parseIMUData(const Json::Value& imu_json, IMUData& imu_data);
};

}  // namespace quadruped_sdk

#endif // QUADRUPED_SDK_JSON_PARSER_H
