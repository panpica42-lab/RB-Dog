#include "quadruped_sdk/udp_client.h"
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <cerrno>

namespace quadruped_sdk {

// 构造函数 - 初始化列表顺序要和声明顺序一致
UDPClient::UDPClient(const std::string& ip, int port) 
    : client_socket(-1),     // 第一个：client_socket
      server_ip(ip),         // 第二个：server_ip
      server_port(port) {    // 第三个：server_port
    // server_addr 在函数体内初始化
    memset(&server_addr, 0, sizeof(server_addr));
    initServerAddress();
}

// 移动构造函数
UDPClient::UDPClient(UDPClient&& other) noexcept
    : client_socket(other.client_socket),
      server_ip(std::move(other.server_ip)),
      server_port(other.server_port),
      server_addr(other.server_addr) {
    // 关键：将原对象的socket置为无效，避免重复关闭
    other.client_socket = -1;
    other.server_port = 0;
    memset(&other.server_addr, 0, sizeof(other.server_addr));
}

// 移动赋值运算符
UDPClient& UDPClient::operator=(UDPClient&& other) noexcept {
    if (this != &other) {
        // 先关闭当前socket
        if (client_socket >= 0) {
            ::close(client_socket);
        }
        
        // 转移资源
        client_socket = other.client_socket;
        server_ip = std::move(other.server_ip);
        server_port = other.server_port;
        server_addr = other.server_addr;
        
        // 将原对象置为无效
        other.client_socket = -1;
        other.server_port = 0;
        memset(&other.server_addr, 0, sizeof(other.server_addr));
    }
    return *this;
}

// 析构函数
UDPClient::~UDPClient() {
    close();
}

// 初始化服务器地址
void UDPClient::initServerAddress() {
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(server_port);
    server_addr.sin_addr.s_addr = inet_addr(server_ip.c_str());
}

// 初始化客户端
bool UDPClient::initialize() {
    // 如果已经初始化，先关闭
    if (client_socket >= 0) {
        close();
    }
    
    // 创建UDP socket
    client_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (client_socket < 0) {
        std::cerr << "创建socket失败: " << strerror(errno) << std::endl;
        return false;
    }
    
    // 可选：设置socket选项
    int opt = 1;
    if (setsockopt(client_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        std::cerr << "警告: 设置SO_REUSEADDR失败: " << strerror(errno) << std::endl;
    }
    
    return true;
}

// 发送消息到服务器
bool UDPClient::sendMessage(const std::string& message) {
    if (client_socket < 0) {
        std::cerr << "客户端未初始化" << std::endl;
        return false;
    }
    
    if (message.empty()) {
        std::cerr << "消息为空" << std::endl;
        return false;
    }
    
    // 发送数据到服务器
    ssize_t sent_len = sendto(client_socket, message.c_str(), message.length(), 0,
                             (struct sockaddr*)&server_addr, sizeof(server_addr));
    
    if (sent_len < 0) {
        std::cerr << "发送失败: " << strerror(errno) << std::endl;
        return false;
    }
    return true;
}

// 接收服务器响应（带超时）
std::string UDPClient::receiveResponse(int timeout_seconds) {
    if (client_socket < 0) {
        return "ERROR: 客户端未初始化";
    }
    
    // 设置超时
    struct timeval tv;
    tv.tv_sec = timeout_seconds;
    tv.tv_usec = 0;
    setsockopt(client_socket, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    
    // 接收数据
    char buffer[BUFFER_SIZE];
    memset(buffer, 0, BUFFER_SIZE);
    socklen_t server_addr_len = sizeof(server_addr);
    
    ssize_t recv_len = recvfrom(client_socket, buffer, BUFFER_SIZE - 1, 0,
                               (struct sockaddr*)&server_addr, &server_addr_len);
    
    if (recv_len < 0) {
        if (errno == EWOULDBLOCK || errno == EAGAIN) {
            return "TIMEOUT: 接收超时";
        }
        return "ERROR: " + std::string(strerror(errno));
    }
    
    buffer[recv_len] = '\0';
    return std::string(buffer);
}

// 发送并接收响应
std::string UDPClient::sendAndReceive(const std::string& message, int timeout_seconds) {
    if (!sendMessage(message)) {
        return "ERROR: 发送失败";
    }
    
    return receiveResponse(timeout_seconds);
}

// 设置超时时间
void UDPClient::setTimeout(int seconds) {
    if (client_socket >= 0) {
        struct timeval tv;
        tv.tv_sec = seconds;
        tv.tv_usec = 0;
        setsockopt(client_socket, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    }
}

// 关闭客户端连接
void UDPClient::close() {
    if (client_socket >= 0) {
        ::close(client_socket);
        client_socket = -1;
        std::cout << "客户端连接已关闭" << std::endl;
    }
}

// 获取服务器信息
std::string UDPClient::getServerInfo() const {
    return server_ip + ":" + std::to_string(server_port);
}

// 检查客户端是否已初始化
bool UDPClient::isInitialized() const {
    return client_socket >= 0;
}

// 测试连接
bool UDPClient::testConnection(int timeout_seconds) {
    bool connectFlag = false;
    std::string response;

    while(!connectFlag){
        std::cout << "Trying to connect udp server..." << std::endl;
        std::string response = sendAndReceive("PING", timeout_seconds);

        if (response.find("ERROR") == 0 || response.find("TIMEOUT") == 0) {
            std::cout << "After 3s connect to udp server again..." << std::endl;
            sleep(3);
        }else{
            connectFlag = true;
        }
    }
    
    std::cout << "=== 成功连接到UDP服务器 ===: " << response << std::endl;
    return true;
}

}  // namespace quadruped_sdk