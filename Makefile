# =============================================
# Quadruped SDK Makefile
# =============================================

# 项目配置
PROJECT_NAME = quadruped_sdk
VERSION = 1.0.0
DOCKER_IMAGE ?= quadruped-sdk:$(VERSION)
DOCKER_IMAGE_LATEST ?= quadruped-sdk:latest
DOCKER_PORT ?= 9001
DOCKER_MOCK_PORT ?= 9101
DOCKER ?= docker

# 目录配置
SRC_DIR = src
INC_DIR = include
LIB_DIR = lib
BIN_DIR = bin
EXAMPLES_DIR = examples
TESTS_DIR = examples

# 编译器配置
CXX = g++
CXXFLAGS = -std=c++11 -Wall -Wextra -pedantic -pthread -I$(INC_DIR) 
LDFLAGS = 
LDLIBS = -ljsoncpp -lm  # 添加-lm用于数学库

# 目标配置
STATIC_LIB = $(LIB_DIR)/lib$(PROJECT_NAME).a
SHARED_LIB = $(LIB_DIR)/lib$(PROJECT_NAME).so

# 源文件
SRC_FILES = $(wildcard $(SRC_DIR)/*.cpp)
OBJ_FILES = $(patsubst $(SRC_DIR)/%.cpp, $(LIB_DIR)/%.o, $(SRC_FILES))

# 示例程序 - 使用列表而不是通配符
EXAMPLES = example keyboard_test imu_client_example
EXAMPLE_BINS = $(addprefix $(BIN_DIR)/, $(EXAMPLES))

# 测试程序
TEST_SRCS = $(wildcard $(TESTS_DIR)/*.cpp)
TEST_BINS = $(patsubst $(TESTS_DIR)/%.cpp, $(BIN_DIR)/%, $(TEST_SRCS))

# 颜色定义
GREEN = \033[0;32m
RED = \033[0;31m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

# 默认目标
all: static examples tests

# 静态库
static: $(STATIC_LIB)

# 共享库（可选）
shared: $(SHARED_LIB)

# 示例程序
examples: $(EXAMPLE_BINS)

# 测试程序
tests: $(TEST_BINS)

# 编译静态库
$(STATIC_LIB): $(OBJ_FILES)
	@echo "$(GREEN)创建静态库 $@...$(NC)"
	@mkdir -p $(LIB_DIR)
	ar rcs $@ $^
	@echo "$(GREEN)✓ 静态库创建完成$(NC)"

# 编译共享库
$(SHARED_LIB): $(OBJ_FILES)
	@echo "$(GREEN)创建共享库 $@...$(NC)"
	@mkdir -p $(LIB_DIR)
	$(CXX) -shared -o $@ $^ $(LDFLAGS) $(LDLIBS)
	@echo "$(GREEN)✓ 共享库创建完成$(NC)"

# 编译对象文件
$(LIB_DIR)/%.o: $(SRC_DIR)/%.cpp
	@echo "$(YELLOW)编译 $<...$(NC)"
	@mkdir -p $(LIB_DIR)
	$(CXX) $(CXXFLAGS) -fPIC -c $< -o $@

# 编译示例程序 - 通用规则
$(BIN_DIR)/%: $(EXAMPLES_DIR)/%.cpp $(STATIC_LIB)
	@echo "$(BLUE)编译示例 $@...$(NC)"
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< $(STATIC_LIB) -o $@ $(LDFLAGS) $(LDLIBS)
	@echo "$(BLUE)✓ 示例编译完成$(NC)"

# 编译测试程序
$(BIN_DIR)/%: $(TESTS_DIR)/%.cpp $(STATIC_LIB)
	@echo "$(GREEN)编译测试 $@...$(NC)"
	@mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $< $(STATIC_LIB) -o $@ $(LDFLAGS) $(LDLIBS)
	@echo "$(GREEN)✓ 测试编译完成$(NC)"

# 安装
install: static shared
	@echo "$(GREEN)安装SDK到系统目录...$(NC)"
	@mkdir -p /usr/local/include/quadruped_sdk
	@cp -r $(INC_DIR)/quadruped_sdk/* /usr/local/include/quadruped_sdk/
	@cp $(STATIC_LIB) /usr/local/lib/
	@cp $(SHARED_LIB) /usr/local/lib/
	@echo "$(GREEN)✓ SDK安装完成$(NC)"

# 卸载
uninstall:
	@echo "$(RED)卸载SDK...$(NC)"
	@rm -rf /usr/local/include/quadruped_sdk
	@rm -f /usr/local/lib/lib$(PROJECT_NAME).*
	@echo "$(RED)✓ SDK卸载完成$(NC)"

# 运行目标
run_example: $(BIN_DIR)/example
	@echo "$(BLUE)运行主示例程序...$(NC)"
	@./$(BIN_DIR)/example

run_keyboard: $(BIN_DIR)/keyboard_test
	@echo "$(GREEN)运行键盘测试程序...$(NC)"
	@./$(BIN_DIR)/keyboard_test

run_imu: $(BIN_DIR)/imu_client_example
	@echo "$(GREEN)运行IMU客户端示例...$(NC)"
	@./$(BIN_DIR)/imu_client_example

run_ws_gateway:
	@echo "$(GREEN)运行WebSocket网页控制网关...$(NC)"
	@python3 tools/ws_gateway.py

run_ws_mock:
	@echo "$(GREEN)运行WebSocket网页控制网关模拟模式...$(NC)"
	@python3 tools/ws_gateway.py --mock

docker_build:
	@echo "$(GREEN)构建Docker镜像 $(DOCKER_IMAGE)...$(NC)"
	$(DOCKER) build -t $(DOCKER_IMAGE) -t $(DOCKER_IMAGE_LATEST) .

docker_run_ws:
	@echo "$(GREEN)运行Docker真实机器狗网关...$(NC)"
	$(DOCKER) run --rm -it --network host \
		-e LISTEN_PORT=$(DOCKER_PORT) \
		$(DOCKER_IMAGE_LATEST) ws

docker_run_mock:
	@echo "$(GREEN)运行Docker模拟网关...$(NC)"
	$(DOCKER) run --rm -it --network host \
		-e LISTEN_PORT=$(DOCKER_MOCK_PORT) \
		$(DOCKER_IMAGE_LATEST) ws-mock

# 清理
clean:
	@echo "$(RED)清理构建文件...$(NC)"
	@rm -rf $(LIB_DIR) $(BIN_DIR)
	@echo "$(RED)✓ 清理完成$(NC)"

# 显示帮助
help:
	@echo "$(GREEN)=== Quadruped SDK 构建系统 ===$(NC)"
	@echo "可用命令:"
	@echo "  make all          - 构建所有目标（默认）"
	@echo "  make static       - 构建静态库"
	@echo "  make shared       - 构建共享库"
	@echo "  make examples     - 构建示例程序"
	@echo "  make tests        - 构建测试程序"
	@echo "  make install      - 安装SDK到系统"
	@echo "  make uninstall    - 卸载SDK"
	@echo "  make run_example  - 运行主示例程序"
	@echo "  make run_keyboard - 运行键盘测试程序"
	@echo "  make run_imu      - 运行IMU客户端示例"
	@echo "  make run_ws_gateway - 运行WebSocket网页控制网关"
	@echo "  make run_ws_mock  - 运行WebSocket网页控制网关模拟模式"
	@echo "  make docker_build - 构建Docker镜像"
	@echo "  make docker_run_ws - 运行Docker真实机器狗网关"
	@echo "  make docker_run_mock - 运行Docker模拟网关"
	@echo "  make clean        - 清理构建文件"
	@echo "  make help         - 显示此帮助信息"
	@echo ""
	@echo "可用的示例程序:"
	@for example in $(EXAMPLES); do \
		echo "  - $$example"; \
	done

.PHONY: all static shared examples tests install uninstall run_example run_keyboard run_imu run_ws_gateway run_ws_mock docker_build docker_run_ws docker_run_mock clean help
