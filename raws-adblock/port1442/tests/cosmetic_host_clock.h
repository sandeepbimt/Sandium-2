// SPDX-License-Identifier: MPL-2.0
#pragma once
#include <functional>
#include <utility>

namespace base {
class TimeTicks {
 public:
  explicit TimeTicks(int seconds) : seconds_(seconds) {}
  static TimeTicks Now() { return TimeTicks(0); }
  int operator-(TimeTicks earlier) const { return seconds_ - earlier.seconds_; }
 private:
  int seconds_;
};
constexpr int Seconds(int seconds) { return seconds; }
class OnceClosure {
 public:
  explicit OnceClosure(std::function<void()> callback)
      : callback_(std::move(callback)) {}
  OnceClosure(OnceClosure&&) = default;
  OnceClosure(OnceClosure const&) = delete;
  void Run() && { std::move(callback_)(); }
 private:
  std::function<void()> callback_;
};
}  // namespace base
