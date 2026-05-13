#ifndef QUADRUPED_SDK_UDP_CLIENT_H
#define QUADRUPED_SDK_UDP_CLIENT_H

#include <string>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
namespace quadruped_sdk {

class UDPClient {
private:
    // 注意：成员变量声明的顺序会影响初始化顺序
    int client_socket;        // 第一个声明
    std::string server_ip;    // 第二个声明
    int server_port;          // 第三个声明
    struct sockaddr_in server_addr;  // 第四个声明
    
    // 常量定义
    static const int BUFFER_SIZE = 1024;
    static const int DEFAULT_TIMEOUT_SECONDS = 5;
    
    // 初始化服务器地址
    void initServerAddress();
    
public:
    // 构造函数
    UDPClient(const std::string& ip = "127.0.0.1", int port = 8080);
    
        // 移动构造函数
    UDPClient(UDPClient&& other) noexcept;
    
    // 移动赋值运算符
    UDPClient& operator=(UDPClient&& other) noexcept;
    
    // 删除拷贝构造函数和赋值运算符
    UDPClient(const UDPClient&) = delete;
    UDPClient& operator=(const UDPClient&) = delete;
    
    // 析构函数
    ~UDPClient();
    
    // 初始化客户端
    bool initialize();
    
    // 发送消息到服务器
    bool sendMessage(const std::string& message);
    
    // 接收服务器响应（带超时）
    std::string receiveResponse(int timeout_seconds = DEFAULT_TIMEOUT_SECONDS);
    
    // 发送并接收响应（组合操作）
    std::string sendAndReceive(const std::string& message, int timeout_seconds = DEFAULT_TIMEOUT_SECONDS);
    
    // 设置超时时间
    void setTimeout(int seconds);
    
    // 关闭客户端连接
    void close();
    
    // 获取服务器信息
    std::string getServerInfo() const;
    
    // 检查客户端是否已初始化
    bool isInitialized() const;
    
    // 测试连接
    bool testConnection(int timeout_seconds = 3);
};

}  // namespace quadruped_sdk

#endif // QUADRUPED_SDK_UDP_CLIENT_H