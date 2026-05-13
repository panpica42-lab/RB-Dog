#include "quadruped_sdk/json_parser.h"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <iomanip>

namespace quadruped_sdk {

JsonParser::JsonParser(UDPClient&& client) 
    : client_(std::move(client)) {
    root_ = Json::objectValue;
}

// 析构函数：确保线程安全退出
JsonParser::~JsonParser() {
    stop(); // 停止后台线程
}

JsonParser::JsonParser(JsonParser&& other) noexcept
    : client_(std::move(other.client_)),
      root_(std::move(other.root_)),
      last_error_(std::move(other.last_error_)),
      break_flag(other.break_flag.load()),
      incomplete_msg_(std::move(other.incomplete_msg_)),
      recv_thread_(std::move(other.recv_thread_)),
      send_thread_(std::move(other.send_thread_)) {
}

JsonParser& JsonParser::operator=(JsonParser&& other) noexcept {
    if (this != &other) {
        client_ = std::move(other.client_);
        root_ = std::move(other.root_);
        last_error_ = std::move(other.last_error_);
        incomplete_msg_ = std::move(other.incomplete_msg_);
        break_flag = other.break_flag.load();
        recv_thread_ = std::move(other.recv_thread_);
        send_thread_ = std::move(other.send_thread_);
    }
    return *this;
}

void JsonParser::run(){
    if (!break_flag && !recv_thread_.joinable()) {
        // 启动后台线程，执行receiveLoop函数
        recv_thread_ = std::thread(&JsonParser::receiveLoop, this);
        std::cout << "后台接收线程已启动" << std::endl;
    }

    if (!break_flag && !send_thread_.joinable()) {
        // 启动后台线程，执行sendLoop函数
        send_thread_ = std::thread(&JsonParser::sendLoop, this);
        std::cout << "后台发送线程已启动" << std::endl;
    }
}

void JsonParser::stop(){
    // 1. 设置退出标志
    break_flag = true;

    // 2. 等待线程退出（必须join，避免线程泄漏）
    if (send_thread_.joinable()) {
        send_thread_.join();
        std::cout << "后台发送线程已停止" << std::endl;
    }

    if (recv_thread_.joinable()) {
        recv_thread_.join();
        std::cout << "后台接收线程已停止" << std::endl;
    }

    // 3. 清空缓存
    std::lock_guard<std::mutex> lock(mutex_);
    incomplete_msg_.clear();
}

// 私有线程函数：持续接收UDP数据（核心）
void JsonParser::receiveLoop() {
    // 设置线程名称（可选，便于调试）
    pthread_setname_np(pthread_self(), "UDP_Recv_Loop");

    while (!break_flag) {
        try {
            // 1. 接收UDP数据（超时1秒，避免阻塞）
            bool parse_success = receiveAndParse(1);

            // 2. 解析成功则分发响应
            if (parse_success) {
                std::lock_guard<std::mutex> lock(mutex_);
                Json::Value response = root_;

                // 根据msg_type分发响应
                if (response.isMember("msg_type")) {
                    int msg_type = response["msg_type"].asInt();
                    switch (msg_type) {
                        case MSG_QUERY_RESPONSE:
                            handleQueryResponse(response);
                            break;
                        case MSG_COMMAND_RESPONSE:
                            handleCommandResponse(response);
                            break;
                        case MSG_IMUDATA_RESPONSE:   // IMU数据
                            handleIMUMessage(response);
                            break;
                        default:
                            last_error_ = "未知的消息类型: " + std::to_string(msg_type);
                            std::cerr << last_error_ << std::endl;
                            break;
                    }
                }
            }

            // 3. 小休眠，降低CPU占用
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        } catch (const std::exception& e) {
            std::cerr << "接收线程异常: " << e.what() << std::endl;
            std::this_thread::sleep_for(std::chrono::seconds(1)); // 异常后休眠1秒，避免频繁报错
        }
    }
}

// 私有线程函数：获取机器狗实时状态
void JsonParser::sendLoop() {
    // 设置线程名称（可选，便于调试）
    pthread_setname_np(pthread_self(), "UDP_Send_Loop");

    // 设置发送频率（Hz）
    const double frequency_hz = 1;  // 1Hz
    const std::chrono::milliseconds interval_ms(static_cast<int>(1000.0 / frequency_hz));
    
    printf("UDP send loop started at %.1f Hz\n", frequency_hz);
    
    int sequence = 0;
    
    while (!break_flag) {
        //continue;
        auto loop_start = std::chrono::steady_clock::now();
        
        sequence++;
        
        // 创建状态查询请求
        Json::Value json_value;
        json_value["msg_type"] = quadruped_sdk::MSG_QUERY_REQUEST;
        json_value["query_code"] = quadruped_sdk::QUERY_REALTIME_STATUS;
        
        // 发送JSON
        sendJson(json_value);
        
        // 计算耗时
        auto loop_end = std::chrono::steady_clock::now();
        auto elapsed_time = std::chrono::duration_cast<std::chrono::milliseconds>(loop_end - loop_start);
        
        // 如果执行时间小于间隔时间，则休眠剩余时间
        if (elapsed_time < interval_ms) {
            std::this_thread::sleep_for(interval_ms - elapsed_time);
        }
    }
    
    printf("UDP send loop stopped");
}

bool JsonParser::parseJsonString(const std::string& json_str) {
    Json::CharReaderBuilder builder;
    std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
    
    last_error_.clear();
    
    bool success = reader->parse(json_str.c_str(), 
                                 json_str.c_str() + json_str.length(), 
                                 &root_, 
                                 &last_error_);
    
    return success;
}

bool JsonParser::receiveAndParse(int timeout_seconds) {
    // 1. 接收UDP数据
    std::string response = client_.receiveResponse(timeout_seconds);
    
    if (response.find("ERROR") == 0 || response.find("TIMEOUT") == 0) {
        last_error_ = "UDP接收失败: " + response;
        return false;
    }

    // 加锁保护incomplete_msg_
    std::lock_guard<std::mutex> lock(mutex_);
    
    // 2. 将新接收的数据追加到不完整消息缓存中
    incomplete_msg_ += response;
    //std::cout << "当前缓存消息：" << incomplete_msg_ << std::endl;  // 调试用，可删除

    // 3. 提取完整的JSON帧
    std::string complete_json = extract_complete_json(incomplete_msg_);
    if (complete_json.empty()) {
        last_error_ = "未接收到完整的JSON帧,暂存数据等待补充";
        std::cerr << last_error_ << std::endl;  // 调试用，可删除
        return false;
    }

    // 4. 解析完整的JSON帧
    // 检查是否是摇杆控制消息（没有msg_type字段）
    //std::cout << "Complete json message: " << complete_json << std::endl;  // 调试用，可删除

    return parseJsonString(complete_json);
}

bool JsonParser::sendJson(const Json::Value& json_value) {
    Json::StreamWriterBuilder builder;
    builder["indentation"] = "";  // 紧凑格式
    std::string json_str = Json::writeString(builder, json_value);

    //printf("Sending request: %s\n", json_str.c_str());

    if (json_str.empty()) {
        last_error_ = "JSON序列化失败";
        return false;
    }
    
    if (!client_.sendMessage(json_str)) {
        last_error_ = "UDP发送失败";
        return false;
    }
    
    return true;
}

bool JsonParser::sendAndReceiveJson(const Json::Value& request, 
                                   Json::Value& response, 
                                   int timeout_seconds) {
    if (!sendJson(request)) {
        return false;
    }
    
    if (!receiveAndParse(timeout_seconds)) {
        return false;
    }
    
    response = root_;
    return true;
}

Json::Value JsonParser::createObject() {
    return Json::objectValue;
}

Json::Value JsonParser::createArray() {
    return Json::arrayValue;
}

void JsonParser::handleSwitchMnnCommand(int mode){
    if(current_status_.motion_mode == MODE_STANDING){
        Json::Value json_value;
        json_value["msg_type"] = MSG_COMMAND_REQUEST;
        json_value["cmd_code"] = CMD_SET_MOTION_MODE;
        json_value["para"] = mode;
        sendJson(json_value);

        currentMode = mode;
    }
}

void JsonParser::handleMotionCommand(int para){
    if(current_status_.motion_mode == MODE_STANDING){
        Json::Value json_value;
        json_value["msg_type"] = MSG_COMMAND_REQUEST;
        json_value["cmd_code"] = CMD_PERFORM_ACTION;
        json_value["para"] = para;
        sendJson(json_value);
    }
}

void JsonParser::handleResetCommand(){
    Json::Value json_value;
    json_value["msg_type"] = MSG_COMMAND_REQUEST;
    json_value["cmd_code"] = CMD_RESET;
    sendJson(json_value);
}

void JsonParser::handleLidarObstacleCommand(int para){
    if(current_status_.motion_mode == MODE_STANDING){
        Json::Value json_value;
        json_value["msg_type"] = MSG_COMMAND_REQUEST;
        json_value["cmd_code"] = CMD_ULTRASONIC_OBSTACLE_AVOIDANCE;
        json_value["para"] = para;
        sendJson(json_value);
    }
}

void JsonParser::handleEmergencyCommand(){
    Json::Value json_value;
    json_value["msg_type"] = MSG_COMMAND_REQUEST;
    json_value["cmd_code"] = CMD_EMERGENCY_STOP;
    sendJson(json_value);
}

void JsonParser::handleStandUpCommand(){
    Json::Value json_value;
    json_value["msg_type"] = MSG_COMMAND_REQUEST;
    json_value["cmd_code"] = CMD_STAND_UP;
    sendJson(json_value);
}

void JsonParser::handleLieDownCommand(){
    Json::Value json_value;
    json_value["msg_type"] = MSG_COMMAND_REQUEST;
    json_value["cmd_code"] = CMD_LIE_DOWN;
    sendJson(json_value);
}

void JsonParser::sendDirectionVel(int direction,double velocity){
    Json::Value json_value;
    json_value["vel_move_frontback"] = 0.0;
    json_value["vel_move_leftright"] = 0.0;
    json_value["vel_turn_leftright"] = 0.0;

    float vel_float = static_cast<float>(velocity);

    switch(direction){
        case 1:
            json_value["vel_move_frontback"] = vel_float;
            break;
        case 2:
            json_value["vel_move_leftright"] = vel_float;
            break;
        case 3:
            json_value["vel_turn_leftright"] = vel_float;
            break;
        default:
            break;
    }

    sendJson(json_value);
}

void JsonParser::sendDirectionVel(double move_frontback, double move_leftright, double turn_leftright){
    // 四舍五入
    double rounded_frontback = std::round(move_frontback * 100.0) / 100.0;
    double rounded_leftright = std::round(move_leftright * 100.0) / 100.0;
    double rounded_turn = std::round(turn_leftright * 100.0) / 100.0;
    
    Json::Value json_value;
    // 强制转换为float
    json_value["vel_move_frontback"] = static_cast<float>(rounded_frontback);
    json_value["vel_move_leftright"] = static_cast<float>(rounded_leftright);
    json_value["vel_turn_leftright"] = static_cast<float>(rounded_turn);

    sendJson(json_value);
}

DogStatus JsonParser::getDogStatus() const{
    std::lock_guard<std::mutex> lock(status_mutex_);
    return current_status_;
}

std::string JsonParser::extract_complete_json(std::string& buffer){
    std::string complete_json;
    int brace_balance = 0;  // {}平衡计数器：{+1，}-1
    size_t start_pos = std::string::npos;

    for (size_t i = 0; i < buffer.size(); ++i) {
        char c = buffer[i];
        if (c == '{') {
            if (brace_balance == 0) {
                start_pos = i;  // 标记完整帧的起始位置
            }
            brace_balance++;
        } else if (c == '}') {
            brace_balance--;
            // 找到完整的JSON帧（{}平衡且起始位置有效）
            if (brace_balance == 0 && start_pos != std::string::npos) {
                complete_json = buffer.substr(start_pos, i - start_pos + 1);
                // 移除已提取的完整帧，剩余部分保留在buffer中（处理粘包）
                buffer.erase(0, i + 1);
                return complete_json;
            }
        }
    }

    // 无完整帧，返回空（buffer中保留不完整数据）
    return "";
}

void JsonParser::parseRealtimeStatus(const Json::Value& json_value){
    try {
        std::lock_guard<std::mutex> lock(status_mutex_);
        // 1. 如果 json_value 确实是对象，直接访问它的字段
        if (json_value.isObject()) {
            // 直接访问 json_value 对象中的字段
            if (json_value.isMember("battery")) {
                int battery = json_value["battery"].asInt();
                //std::cout << "Battery: " << battery << "%" << std::endl;
                current_status_.battery_level = battery;
            }
            
            if (json_value.isMember("hardware_error")) {
                int hardware_error = json_value["hardware_error"].asInt();
                //std::cout << "Hardware error: " << hardware_error << std::endl;
                current_status_.hardware_error = hardware_error;
            }
            
            if (json_value.isMember("robot_type") && json_value["robot_type"].isString()) {
                std::string robot_type = json_value["robot_type"].asString();
                //std::cout << "Robot type: " << robot_type << std::endl;
                current_status_.robot_type = robot_type;
            }
            
            if (json_value.isMember("robot_number") && json_value["robot_number"].isString()) {
                std::string robot_number = json_value["robot_number"].asString();
                //std::cout << "Robot number: " << robot_number << std::endl;
                current_status_.robot_number = robot_number;
            }
            
            if (json_value.isMember("software_version")) {
                std::string sf_version = json_value["software_version"].asString();
                float software_version = std::stof(sf_version);
                //std::cout << "Software version: " << software_version << std::endl;
                current_status_.software_version = software_version;
            }

            if (json_value.isMember("latest_version")) {
                std::string version = json_value["software_version"].asString();
                float latest_version = std::stof(version);
                //std::cout << "Software latest_version: " << latest_version << std::endl;
                current_status_.latest_software_version = latest_version;
            }

            if (json_value.isMember("protocol_version")) {
                double protocol_version = json_value["protocol_version"].asDouble();
                //std::cout << "protocol_version: " << protocol_version << std::endl;
                current_status_.protocol_version = protocol_version;
            }

            if (json_value.isMember("motion_mode")) {
                float motion_mode = json_value["motion_mode"].asFloat();
                //std::cout << "motion_mode: " << motion_mode << std::endl;
                current_status_.motion_mode = motion_mode;
            }

            if (json_value.isMember("velocity_level")) {
                int velocity_level = json_value["velocity_level"].asInt();
                //std::cout << "velocity_level: " << velocity_level << std::endl;
                current_status_.velocity_level = velocity_level;
            }

            if (json_value.isMember("model")) {
                int model = json_value["model"].asInt();
                //std::cout << "model: " << model << std::endl;
                current_status_.model = model;
            }

            if (json_value.isMember("hw_failure")) {
                std::vector<int> array;
                const Json::Value& hw_failure = json_value["hw_failure"];
            
                if (hw_failure.isArray()) {
                    if (hw_failure.size() > 0) {
                        
                        //std::cout << "Hardware failures (" << hw_failure.size() << "):" << std::endl;
                    
                        for (Json::ArrayIndex i = 0; i < hw_failure.size(); i++) {
                            std::string failure_desc;

                            if (hw_failure[i].isInt()) {
                                array.push_back(hw_failure[i].asInt());
                                failure_desc = "Error code: " + std::to_string(hw_failure[i].asInt());
                            }
                        
                            std::cout << "  [" << i + 1 << "] " << failure_desc << std::endl;
                        }

                        current_status_.hw_failures = array;
                    
                        // 根据故障数量设置状态
                        if (hw_failure.size() > 3) {
                            //std::cerr << "WARNING: Multiple hardware failures detected!" << std::endl;
                        }
                    } else {
                        //std::cout << "Hardware failures: []" << std::endl;
                    }
                } else if (hw_failure.isString()) {
                    // 有些API可能返回字符串而不是数组
                    std::string failure_str = hw_failure.asString();
                    if (!failure_str.empty()) {
                        //std::cout << "Hardware failure: " << failure_str << std::endl;
                    }
                }
            }
        }
    } catch (const Json::Exception& e) {
        std::cerr << "JSON exception: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
    }
}

void JsonParser::handleQueryResponse(const Json::Value& response) {
    int query_code = response["query_code"].asInt();
    if(query_code == 1){
        const Json::Value& result_obj = response["result"];
        parseRealtimeStatus(result_obj);
    }
}

void JsonParser::handleCommandResponse(const Json::Value& response){
    int cmd_code = response["cmd_code"].asInt();
    int result = response["result"].asInt();
    printf("Handling command response, code: %d, result: %d\n", cmd_code, result);

    switch (cmd_code) {
        case CMD_SET_VELOCITY_LEVEL:
            if(result == 1){
                std::lock_guard<std::mutex> lock(status_mutex_);
                current_status_.velocity_level = velocity_level;
            }
            break;
        case CMD_SET_MOTION_MODE:
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                if(result == 1){
                    current_status_.model = currentMode;
                }else{
                    currentMode = !currentMode;
                    current_status_.model = currentMode;
                }
            }
            break;
        case CMD_PERFORM_ACTION:
            {
                std::lock_guard<std::mutex> lock(status_mutex_);
                if(result == 1){
                    current_status_.motion_mode = MODE_STANDING;
                }
            }
            break;
        case CMD_RESET:
            if(result == 1){
                std::lock_guard<std::mutex> lock(status_mutex_);
                current_status_.motion_mode = MODE_STANDING;
            }
            break;
        case CMD_ULTRASONIC_OBSTACLE_AVOIDANCE:
            break;
        case CMD_EMERGENCY_STOP:
            // handleEmergencyCommand();
            break;
        case CMD_UPDATE_SOFTWARE:
            break;
        case CMD_RECOVER_FROM_FALL:
            break;
        case CMD_CAMERA_STREAM:
            break;
        case CMD_STAND_UP:
            if(result == 1){
                std::lock_guard<std::mutex> lock(status_mutex_);
                current_status_.motion_mode = MODE_STANDING;
            }
            break;
        case CMD_LIE_DOWN:
            if(result == 1){
                std::lock_guard<std::mutex> lock(status_mutex_);
                current_status_.motion_mode = MODE_LYING_DOWN;
            }
            break;
        default:
            printf("Unknown command code: %d", cmd_code);
            break;
    }
}

// 实现
void JsonParser::setIMUDataCallback(IMUDataCallback callback) {
    imu_callback_ = callback;
}

bool JsonParser::enableIMUStream() {
    if (imu_stream_enabled_) {
        return true;
    }
    
    // 发送注册命令到服务器
    Json::Value json_value;
    json_value["msg_type"] = 3;  // 命令请求
    json_value["cmd_code"] = 20; // 注册IMU客户端
    
    if (sendJson(json_value)) {
        imu_stream_enabled_ = true;
        std::cout << "IMU stream enabled" << std::endl;
        return true;
    }
    
    std::cerr << "Failed to enable IMU stream" << std::endl;
    return false;
}

bool JsonParser::disableIMUStream() {
    if (!imu_stream_enabled_) {
        return true;
    }
    
    // 发送注销命令到服务器
    Json::Value json_value;
    json_value["msg_type"] = 3;  // 命令请求
    json_value["cmd_code"] = 21; // 注销IMU客户端
    
    if (sendJson(json_value)) {
        imu_stream_enabled_ = false;
        std::cout << "IMU stream disabled" << std::endl;
        return true;
    }
    
    std::cerr << "Failed to disable IMU stream" << std::endl;
    return false;
}

IMUData JsonParser::getLatestIMUData() const {
    std::lock_guard<std::mutex> lock(imu_mutex_);
    return latest_imu_;
}

void JsonParser::handleIMUMessage(const Json::Value& json_data) {
    try {
        IMUData imu_data;
        
        if (parseIMUData(json_data, imu_data)) {
            // 更新最新IMU数据
            {
                std::lock_guard<std::mutex> lock(imu_mutex_);
                latest_imu_ = imu_data;
            }
            
            // 调用回调函数
            if (imu_callback_) {
                imu_callback_(imu_data);
            }
            
            // 调试输出
            static int counter = 0;
            if (counter++ % 100 == 0) {
                auto euler = imu_data.getEulerAngles();
                std::cout << "IMU Data - Accel: (" 
                         << imu_data.linear_acceleration.x << ", "
                         << imu_data.linear_acceleration.y << ", "
                         << imu_data.linear_acceleration.z << ") m/s², "
                         << "RPY: (" 
                         << euler.roll * 180.0 / M_PI << ", "
                         << euler.pitch * 180.0 / M_PI << ", "
                         << euler.yaw * 180.0 / M_PI << ") deg"
                         << std::endl;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error handling IMU message: " << e.what() << std::endl;
    }
}

bool JsonParser::parseIMUData(const Json::Value& imu_json, IMUData& imu_data) {
    try {
        // 检查消息类型
        if (!imu_json.isMember("msg_type") || imu_json["msg_type"].asInt() != 5) {
            return false;
        }
        
        // 时间戳
        if (imu_json.isMember("timestamp")) {
            imu_data.ros_timestamp = imu_json["timestamp"].asDouble();
            // 转换为系统时间戳
            auto duration = std::chrono::duration<double>(imu_data.ros_timestamp);
            imu_data.timestamp = std::chrono::system_clock::time_point(
                std::chrono::duration_cast<std::chrono::system_clock::duration>(duration));
        }
        
        // 坐标系ID
        if (imu_json.isMember("frame_id") && imu_json["frame_id"].isString()) {
            imu_data.frame_id = imu_json["frame_id"].asString();
        }
        
        // 线性加速度
        if (imu_json.isMember("linear_acceleration")) {
            const Json::Value& accel = imu_json["linear_acceleration"];
            if (accel.isMember("x")) imu_data.linear_acceleration.x = accel["x"].asFloat();
            if (accel.isMember("y")) imu_data.linear_acceleration.y = accel["y"].asFloat();
            if (accel.isMember("z")) imu_data.linear_acceleration.z = accel["z"].asFloat();
        }
        
        // 角速度
        if (imu_json.isMember("angular_velocity")) {
            const Json::Value& gyro = imu_json["angular_velocity"];
            if (gyro.isMember("x")) imu_data.angular_velocity.x = gyro["x"].asFloat();
            if (gyro.isMember("y")) imu_data.angular_velocity.y = gyro["y"].asFloat();
            if (gyro.isMember("z")) imu_data.angular_velocity.z = gyro["z"].asFloat();
        }
        
        // 四元数姿态
        if (imu_json.isMember("orientation")) {
            const Json::Value& orient = imu_json["orientation"];
            if (orient.isMember("w")) imu_data.orientation.w = orient["w"].asFloat();
            if (orient.isMember("x")) imu_data.orientation.x = orient["x"].asFloat();
            if (orient.isMember("y")) imu_data.orientation.y = orient["y"].asFloat();
            if (orient.isMember("z")) imu_data.orientation.z = orient["z"].asFloat();
        }
        
        // 协方差矩阵
        auto parseCovariance = [](const Json::Value& cov_json, std::vector<double>& cov) {
            if (cov_json.isArray() && cov_json.size() == 9) {
                cov.clear();
                for (int i = 0; i < 9; i++) {
                    cov.push_back(cov_json[i].asDouble());
                }
                return true;
            }
            return false;
        };
        
        if (imu_json.isMember("orientation_covariance")) {
            parseCovariance(imu_json["orientation_covariance"], 
                           imu_data.orientation_covariance);
        }
        
        if (imu_json.isMember("angular_velocity_covariance")) {
            parseCovariance(imu_json["angular_velocity_covariance"], 
                           imu_data.angular_velocity_covariance);
        }
        
        if (imu_json.isMember("linear_acceleration_covariance")) {
            parseCovariance(imu_json["linear_acceleration_covariance"], 
                           imu_data.linear_acceleration_covariance);
        }
        
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Error parsing IMU data: " << e.what() << std::endl;
        return false;
    }
}

}  // namespace quadruped_sdk