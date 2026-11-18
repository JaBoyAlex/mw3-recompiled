// SPDX-License-Identifier: GPL-3.0-only
// Original public-API platform contracts. Guest kernel/TLS/r13 are separate.
#include <catch2/catch_test_macros.hpp>
#include <rex/platform/sync.h>
#include <rex/platform/thread.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <memory>
#include <numeric>
#include <vector>
using namespace std::chrono_literals;
namespace p=rex::platform;
namespace {
struct OwnedThread {
  std::unique_ptr<p::Thread> thread;
  std::function<void()> unblock;
  ~OwnedThread() {
    if(unblock) unblock();
    if(thread && p::Wait(thread.get(),false,3s)!=p::WaitResult::kSuccess) {
      std::fputs("THREAD_OWNED_SHUTDOWN_FAILED\n",stderr);std::fflush(stderr);
      std::_Exit(3); // Failure only; never evidence of successful teardown.
    }
  }
};
}

TEST_CASE("original platform: event semantics, semaphore limits and recursive mutex", "[mw3][platform]") {
  auto manual=p::Event::CreateManualResetEvent(false);
  auto automatic=p::Event::CreateAutoResetEvent(false);
  auto semaphore=p::Semaphore::Create(0,2);
  auto mutex=p::Mutant::Create(false);
  REQUIRE(manual);REQUIRE(automatic);REQUIRE(semaphore);REQUIRE(mutex);
  CHECK(p::Wait(manual.get(),false,0ms)==p::WaitResult::kTimeout);
  manual->Set();
  CHECK(p::Wait(manual.get(),false,0ms)==p::WaitResult::kSuccess);
  CHECK(p::Wait(manual.get(),false,0ms)==p::WaitResult::kSuccess);
  manual->Reset();CHECK(p::Wait(manual.get(),false,0ms)==p::WaitResult::kTimeout);
  automatic->Set();CHECK(p::Wait(automatic.get(),false,0ms)==p::WaitResult::kSuccess);
  CHECK(p::Wait(automatic.get(),false,0ms)==p::WaitResult::kTimeout);
  int previous=-1;
  REQUIRE(semaphore->Release(2,&previous));CHECK(previous==0);
  CHECK_FALSE(semaphore->Release(1,nullptr));
  CHECK(p::Wait(semaphore.get(),false,0ms)==p::WaitResult::kSuccess);
  CHECK(p::Wait(semaphore.get(),false,0ms)==p::WaitResult::kSuccess);
  CHECK(p::Wait(semaphore.get(),false,0ms)==p::WaitResult::kTimeout);
  REQUIRE(p::Wait(mutex.get(),false,1s)==p::WaitResult::kSuccess);
  REQUIRE(p::Wait(mutex.get(),false,1s)==p::WaitResult::kSuccess);
  CHECK(mutex->Release());CHECK(mutex->Release());CHECK_FALSE(mutex->Release());
}

TEST_CASE("original platform: suspended start has counted resume and bounded completion", "[mw3][platform]") {
  std::atomic<bool> ran=false;
  p::Thread::CreationParameters parameters;parameters.create_suspended=true;
  OwnedThread worker{p::Thread::Create(parameters,[&]{ran.store(true,std::memory_order_release);}),{}};
  REQUIRE(worker.thread);
  CHECK(p::Wait(worker.thread.get(),false,0ms)==p::WaitResult::kTimeout);
  CHECK_FALSE(ran.load(std::memory_order_acquire));
  rex::u32 previous=0;
  REQUIRE(worker.thread->Suspend(&previous));CHECK(previous==1);
  REQUIRE(worker.thread->Resume(&previous));CHECK(previous==2);
  CHECK(p::Wait(worker.thread.get(),false,0ms)==p::WaitResult::kTimeout);
  REQUIRE(worker.thread->Resume(&previous));CHECK(previous==1);
  REQUIRE(p::Wait(worker.thread.get(),false,3s)==p::WaitResult::kSuccess);
  CHECK(ran.load(std::memory_order_acquire));
}

TEST_CASE("original platform: host TLS isolates concurrent threads and publication", "[mw3][platform]") {
  const auto slot=p::AllocateTLSHandle();REQUIRE(slot!=p::kInvalidTLSHandle);
  struct Slot {p::TLSHandle value;~Slot(){p::FreeTLSHandle(value);}} owned_slot{slot};
  REQUIRE(p::SetTLSValue(slot,0x55));
  auto ready=p::Semaphore::Create(0,8);auto gate=p::Event::CreateManualResetEvent(false);
  REQUIRE(ready);REQUIRE(gate);
  std::array<std::atomic<unsigned>,8> observations{};
  std::vector<std::unique_ptr<OwnedThread>> workers;
  for(unsigned i=0;i<8;++i) {
    auto owner=std::make_unique<OwnedThread>();owner->unblock=[&]{gate->Set();};
    owner->thread=p::Thread::Create({},[&,i] {
      bool valid=p::GetTLSValue(slot)==0 && p::SetTLSValue(slot,0x100+i);
      valid=ready->Release(1,nullptr)&&valid;
      valid=(p::Wait(gate.get(),false,3s)==p::WaitResult::kSuccess)&&valid;
      valid=(p::GetTLSValue(slot)==0x100+i)&&valid;
      observations[i].store(valid?1:2,std::memory_order_release);
    });
    REQUIRE(owner->thread);workers.push_back(std::move(owner));
  }
  for(unsigned i=0;i<8;++i) REQUIRE(p::Wait(ready.get(),false,3s)==p::WaitResult::kSuccess);
  CHECK(p::GetTLSValue(slot)==0x55);gate->Set();
  for(auto& owner:workers) REQUIRE(p::Wait(owner->thread.get(),false,3s)==p::WaitResult::kSuccess);
  for(auto& observation:observations) CHECK(observation.load(std::memory_order_acquire)==1);
}

TEST_CASE("original platform: seeded mutex contention preserves every payload", "[mw3][platform]") {
  auto gate=p::Event::CreateManualResetEvent(false);auto ready=p::Semaphore::Create(0,4);
  auto mutex=p::Mutant::Create(false);REQUIRE(gate);REQUIRE(ready);REQUIRE(mutex);
  std::array<std::array<unsigned,256>,4> payloads{};
  std::uint64_t expected=0,counter=0;unsigned seed=0x12345678;
  for(auto& payload:payloads) for(auto& value:payload) {
    seed=seed*1664525u+1013904223u;value=(seed>>16)&255;expected+=value;
  }
  std::atomic<unsigned> errors=0;
  std::vector<std::unique_ptr<OwnedThread>> workers;
  for(unsigned i=0;i<4;++i) {
    auto owner=std::make_unique<OwnedThread>();owner->unblock=[&]{gate->Set();};
    owner->thread=p::Thread::Create({},[&,i] {
      if(!ready->Release(1,nullptr)||p::Wait(gate.get(),false,3s)!=p::WaitResult::kSuccess) {++errors;return;}
      for(const auto value:payloads[i]) {
        if(p::Wait(mutex.get(),false,3s)!=p::WaitResult::kSuccess) {++errors;return;}
        counter+=value;
        if(!mutex->Release()) {++errors;return;}
      }
    });
    REQUIRE(owner->thread);workers.push_back(std::move(owner));
  }
  for(unsigned i=0;i<4;++i) REQUIRE(p::Wait(ready.get(),false,3s)==p::WaitResult::kSuccess);
  gate->Set();
  for(auto& owner:workers) REQUIRE(p::Wait(owner->thread.get(),false,3s)==p::WaitResult::kSuccess);
  CHECK(errors.load()==0);CHECK(counter==expected);
}

TEST_CASE("original platform: an alertable wait dispatches a queued callback", "[mw3][platform]") {
  auto ready=p::Semaphore::Create(0,1);auto never=p::Event::CreateManualResetEvent(false);
  REQUIRE(ready);REQUIRE(never);std::atomic<unsigned> called=0,result=0;
  OwnedThread worker{p::Thread::Create({},[&] {
    ready->Release(1,nullptr);
    const auto wait=p::Wait(never.get(),true,3s);
    result.store(wait==p::WaitResult::kUserCallback?1:2,std::memory_order_release);
  }),[&]{never->Set();}};
  REQUIRE(worker.thread);REQUIRE(p::Wait(ready.get(),false,3s)==p::WaitResult::kSuccess);
  worker.thread->QueueUserCallback([&]{++called;});
  REQUIRE(p::Wait(worker.thread.get(),false,3s)==p::WaitResult::kSuccess);
  CHECK(called.load()==1);CHECK(result.load(std::memory_order_acquire)==1);
}
