---
title: "Jackson 静默修正非法日期并截断整数入参的小数"
stack: "java"
platform: ["backend"]
versions: ["Java 17.0.21", "Spring Boot 3.2.1", "Jackson Databind 2.15.3", "Jackson JSR310 2.15.3"]
tags: ["jackson", "json", "validation", "localdate", "coercion", "regression-test"]
project: "java-backend"
status: "solved"
date: "2026-11-10"
---

## 现象

JSON 输入没有报错，却在绑定为 Java 对象时被改变；后续 Bean Validation 和业务校验只看到转换后的值，可能将非用户原意的数据保存。

使用以下请求模型及默认转换配置复现（示例已改为通用字段）：

```java
public class Input {
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    @NotNull
    public LocalDate date;

    @Min(1)
    @Max(999999)
    public Integer limit;
}
```

| JSON 输入 | 绑定后的值 | 问题 |
|---|---|---|
| `{"date":"2026-02-30"}` | `2026-02-28` | 非法日期被校正 |
| `{"date":"2026-02-29"}` | `2026-02-28` | 非闰年日期被校正 |
| `{"date":"2026-04-31"}` | `2026-04-30` | 非法月末日期被校正 |
| `{"limit":200.9}` | `200` | 小数部分被丢弃 |
| `{"limit":999999.9}` | `999999` | 截断后仍通过上限校验 |

这里描述的是已验证版本中**自定义日期 pattern 配合默认宽松/SMART 解析**，以及**开启浮点转整数转换**时的行为，不是所有日期格式或所有 Jackson 配置的通用结论。

## 原因

1. 在该 Jackson JSR310 版本中，自定义 pattern 创建的格式化器，在没有明确关闭宽松解析时沿用 SMART 解析风格，部分不存在的月末日期会被解析成合法日期。`@JsonFormat` 指定了文本样式，并不等于已经落实真实日历有效性校验。
2. Jackson 的 `DeserializationFeature.ACCEPT_FLOAT_AS_INT` 默认开启，允许 JSON 浮点数转为整数并丢弃小数部分。
3. Bean Validation 在 JSON 绑定后执行。原始非法日期和小数信息已丢失，`@NotNull`、`@Min`、`@Max` 无法还原原输入并拒绝它们。

`DateTimeFormatter.ofPattern` 默认使用 SMART；需要自定义 formatter 时，应显式设置 `ResolverStyle.STRICT`。这是 Java 日期解析的配置属性，不能只检查输出样式。[Java 17 DateTimeFormatter 文档](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/time/format/DateTimeFormatter.html)

## 解决方案

### 日期：保留严格的 ISO 日历解析

对只需要 `YYYY-MM-DD` 的请求字段，移除上述自定义 pattern，使用已注册 JavaTimeModule 的默认 ISO LocalDate 解析，并保留非空与业务日期范围校验：

```java
@NotNull
private LocalDate date;
```

本次通过真实 Spring HTTP 绑定验证：三个非法日期均被拒绝，合法闰日 `2024-02-29` 仍可保存。

若必须使用自定义格式，应显式配置严格的日期 formatter/反序列化器，并在真实应用 ObjectMapper 上验证；使用 `uuuu` 表示公历年份，避免直接将 `yyyy`（year-of-era）与严格解析组合后引入缺失 era 的问题。不要把一处移除 pattern 当作覆盖了所有项目自定义 ObjectMapper 的保证。

### 整数：关闭浮点数的隐式截断

Spring Boot 配置：

```yaml
spring:
  jackson:
    deserialization:
      accept-float-as-int: false
```

独立使用 ObjectMapper 时，在首次读写前配置：

```java
mapper.disable(DeserializationFeature.ACCEPT_FLOAT_AS_INT);
```

这样小数 JSON 输入会在绑定阶段失败，不再先截断后通过整数范围校验。该配置不代替 `@Min`/`@Max`，也不等于禁止所有字符串到数字的转换；需要更广泛的类型严格性时另行核对 CoercionConfig 与应用契约。[Jackson 2.15.3 DeserializationFeature 源码](https://github.com/FasterXML/jackson-databind/blob/jackson-databind-2.15.3/src/main/java/com/fasterxml/jackson/databind/DeserializationFeature.java)

### 回归测试：经过 HTTP/JSON 绑定，并确认没有写入

- 三个非法日期应返回约定的参数错误，记录数保持不变。
- 合法闰日 `2024-02-29` 应成功，并原样保存/返回。
- 已保存整数值为 `200` 后，分别提交 `200.9`、`999999.9`，均应失败；重新查询仍为 `200`。
- 失败断言必须核对约定的 HTTP 状态和具体业务码；不能把任意 HTTP 500 或内部错误码当作“已拒绝”。
- 不能只手动构造 Java DTO 调 Service：那会跳过最关键的 JSON 反序列化过程。

## 验证与适用范围

上述修复在标注版本的 Spring Boot 应用中通过真实 ObjectMapper、HTTP 控制器绑定和隔离数据库回归测试，上述两组输入回归均通过。未验证的 Jackson 大版本、全局自定义日期模块或单字段反序列化器，需要按相同用例重新确认。

## 相关链接

- [Java 17 DateTimeFormatter：pattern 与解析风格](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/time/format/DateTimeFormatter.html)
- [Jackson 2.15.3 浮点转整数开关及默认值](https://github.com/FasterXML/jackson-databind/blob/jackson-databind-2.15.3/src/main/java/com/fasterxml/jackson/databind/DeserializationFeature.java)
